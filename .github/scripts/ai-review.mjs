#!/usr/bin/env node

// AI Code Review script — calls Azure GPT-5.3 to review PR diffs
// and posts inline review comments via the GitHub API.

import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

// ---------------------------------------------------------------------------
// Environment
// ---------------------------------------------------------------------------

const {
  AZURE_OPENAI_ENDPOINT, // https://....openai.azure.com/openai/v1
  AZURE_OPENAI_API_KEY,
  GITHUB_TOKEN,
  PR_NUMBER,
  REPO,
  HEAD_SHA,
  USER_INSTRUCTIONS = '',
} = process.env;

for (const key of ['AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY', 'GITHUB_TOKEN', 'PR_NUMBER', 'REPO', 'HEAD_SHA']) {
  if (!process.env[key]) {
    console.error(`Missing required env var: ${key}`);
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_FILES = 25;
const MAX_FILE_LINES = 800;
const MAX_DIFF_CHARS = 120_000;
const MODEL = 'gpt-5.3-chat';

// ---------------------------------------------------------------------------
// 1. Fetch PR diff and changed file list
// ---------------------------------------------------------------------------

console.log(`Reviewing PR #${PR_NUMBER} on ${REPO} (${HEAD_SHA.slice(0, 8)})`);

let diff = exec(`gh pr diff ${PR_NUMBER} --repo ${REPO}`);
if (diff.length > MAX_DIFF_CHARS) {
  console.warn(`Diff truncated from ${diff.length} to ${MAX_DIFF_CHARS} chars`);
  diff = diff.slice(0, MAX_DIFF_CHARS) + '\n... (truncated)';
}

const { files } = JSON.parse(exec(`gh pr view ${PR_NUMBER} --repo ${REPO} --json files`));
console.log(`Changed files: ${files.length}`);

// ---------------------------------------------------------------------------
// 2. Read changed files for full context
// ---------------------------------------------------------------------------

const fileContents = {};
for (const file of files.slice(0, MAX_FILES)) {
  try {
    const content = readFileSync(file.path, 'utf8');
    const lines = content.split('\n');
    if (lines.length > MAX_FILE_LINES) {
      fileContents[file.path] = lines.slice(0, MAX_FILE_LINES).join('\n') + `\n... (${lines.length - MAX_FILE_LINES} lines omitted)`;
    } else {
      fileContents[file.path] = content;
    }
  } catch {
    // File deleted or binary — skip
  }
}

// ---------------------------------------------------------------------------
// 3. Build the diff-to-line mapping for inline comments
// ---------------------------------------------------------------------------

const diffLineMap = buildDiffLineMap(diff);

// ---------------------------------------------------------------------------
// 4. Build prompt
// ---------------------------------------------------------------------------

const systemPrompt = `You are an expert code reviewer for CiviQs repositories. Analyze the PR diff and provide actionable feedback.

RESPONSE FORMAT — reply with a single JSON object (no markdown fences):
{
  "summary": "Brief overall assessment (2-4 sentences)",
  "verdict": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
  "comments": [
    {
      "path": "relative/file/path.ext",
      "line": 42,
      "body": "Description of the issue.\\n\\n\`\`\`suggestion\\ncorrected code here\\n\`\`\`"
    }
  ]
}

RULES:
- "line" must reference a LINE NUMBER IN THE NEW VERSION of the file (right side of the diff)
- Only comment on lines that appear in the diff (added or modified lines)
- Use GitHub suggestion syntax (\`\`\`suggestion ... \`\`\`) when you can provide a concrete fix
- Focus on: bugs, security vulnerabilities, error handling, race conditions, logic errors
- Do NOT nitpick style, formatting, or naming conventions unless they cause confusion
- If everything looks good, return verdict "APPROVE" with an empty comments array
- Keep comments concise and actionable
- Maximum 15 comments — prioritize the most important issues`;

const userMessage = buildUserMessage(diff, fileContents, USER_INSTRUCTIONS);

// ---------------------------------------------------------------------------
// 5. Call Azure OpenAI (v1 Chat Completions)
// ---------------------------------------------------------------------------

console.log('Calling Azure GPT-5.3...');

const apiResponse = await fetch(`${AZURE_OPENAI_ENDPOINT}/chat/completions`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${AZURE_OPENAI_API_KEY}`,
  },
  body: JSON.stringify({
    model: MODEL,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userMessage },
    ],
    max_completion_tokens: 16384,
  }),
});

if (!apiResponse.ok) {
  const errText = await apiResponse.text();
  console.error(`Azure API error ${apiResponse.status}: ${errText}`);
  process.exit(1);
}

const apiResult = await apiResponse.json();
const rawContent = apiResult.choices?.[0]?.message?.content;

if (!rawContent) {
  console.error('No content in API response');
  console.error(JSON.stringify(apiResult, null, 2));
  process.exit(1);
}

console.log(`Tokens — prompt: ${apiResult.usage?.prompt_tokens}, completion: ${apiResult.usage?.completion_tokens}`);

// ---------------------------------------------------------------------------
// 6. Parse AI response
// ---------------------------------------------------------------------------

let review;
try {
  // Strip markdown code fences if the model wraps them anyway
  const cleaned = rawContent.replace(/^```(?:json)?\s*\n?/m, '').replace(/\n?```\s*$/m, '');
  review = JSON.parse(cleaned);
} catch (err) {
  console.error('Failed to parse AI response as JSON:', err.message);
  console.error('Raw response:', rawContent.slice(0, 2000));
  // Fall back: post the raw response as a PR comment
  await ghApi(`repos/${REPO}/issues/${PR_NUMBER}/comments`, { body: `## AI Review\n\n${rawContent}` });
  process.exit(0);
}

// ---------------------------------------------------------------------------
// 7. Post PR review with inline comments
// ---------------------------------------------------------------------------

const event = review.verdict === 'APPROVE' ? 'APPROVE'
  : review.verdict === 'REQUEST_CHANGES' ? 'REQUEST_CHANGES'
  : 'COMMENT';

// Filter comments to only those that map to valid diff positions
const validComments = [];
const skippedComments = [];

for (const c of (review.comments || [])) {
  const key = `${c.path}:${c.line}`;
  if (diffLineMap.has(key)) {
    validComments.push({
      path: c.path,
      line: c.line,
      side: 'RIGHT',
      body: c.body,
    });
  } else {
    // Try nearby lines (model may be off by 1-2)
    let placed = false;
    for (const offset of [1, -1, 2, -2]) {
      const nearbyKey = `${c.path}:${c.line + offset}`;
      if (diffLineMap.has(nearbyKey)) {
        validComments.push({
          path: c.path,
          line: c.line + offset,
          side: 'RIGHT',
          body: c.body,
        });
        placed = true;
        break;
      }
    }
    if (!placed) {
      skippedComments.push(c);
    }
  }
}

// Build review body
let body = `## AI Review\n\n${review.summary}`;
if (skippedComments.length > 0) {
  body += '\n\n### Additional comments\n\n';
  for (const c of skippedComments) {
    body += `**${c.path}:${c.line}** — ${c.body}\n\n`;
  }
}

const reviewPayload = {
  commit_id: HEAD_SHA,
  body,
  event,
  comments: validComments,
};

console.log(`Posting review: ${event}, ${validComments.length} inline + ${skippedComments.length} in body`);

await ghApi(`repos/${REPO}/pulls/${PR_NUMBER}/reviews`, reviewPayload);

console.log('Review posted successfully.');

// ===========================================================================
// Helpers
// ===========================================================================

function exec(cmd) {
  return execSync(cmd, { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 });
}

async function ghApi(path, data) {
  const res = await fetch(`https://api.github.com/${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `token ${GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const text = await res.text();
    console.error(`GitHub API error ${res.status} on ${path}: ${text}`);
    // Don't exit — best-effort posting
  }
  return res;
}

function buildUserMessage(diff, fileContents, instructions) {
  let msg = '';

  // Extract the actual instruction (strip @ai-review prefix)
  const cleanInstructions = instructions
    .replace(/@ai-review\s*/gi, '')
    .trim();

  if (cleanInstructions) {
    msg += `## User instructions\n\n${cleanInstructions}\n\n`;
  }

  msg += `## PR Diff\n\n\`\`\`diff\n${diff}\n\`\`\`\n\n`;

  if (Object.keys(fileContents).length > 0) {
    msg += `## Full file contents (for context)\n\n`;
    for (const [path, content] of Object.entries(fileContents)) {
      msg += `### ${path}\n\`\`\`\n${content}\n\`\`\`\n\n`;
    }
  }

  return msg;
}

/**
 * Parse a unified diff and build a Set of "path:line" keys for lines that
 * appear on the RIGHT side (new version). This lets us validate that inline
 * comments target lines actually present in the diff.
 */
function buildDiffLineMap(diff) {
  const map = new Set();
  let currentFile = null;
  let rightLine = 0;

  for (const line of diff.split('\n')) {
    // Detect file header: +++ b/path/to/file
    if (line.startsWith('+++ b/')) {
      currentFile = line.slice(6);
      continue;
    }
    // Detect hunk header: @@ -old,count +new,count @@
    const hunkMatch = line.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
    if (hunkMatch) {
      rightLine = parseInt(hunkMatch[1], 10);
      continue;
    }
    if (!currentFile) continue;

    if (line.startsWith('+')) {
      map.add(`${currentFile}:${rightLine}`);
      rightLine++;
    } else if (line.startsWith('-')) {
      // Deleted line — don't increment right counter
    } else {
      // Context line
      rightLine++;
    }
  }

  return map;
}
