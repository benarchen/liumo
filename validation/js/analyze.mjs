// Offline syntax only. Input code is never evaluated, imported or executed.
import fs from 'node:fs';
import {parse} from 'acorn';

const INPUT_LIMIT = 9 * 1024 * 1024;
const SOURCE_LIMIT = 4 * 1024 * 1024;
const NODE_LIMIT = 200000;
const endpoints = {'/mp/appmsg_comment': 'comment', '/mp/getappmsgext': 'article_ext'};
const pair = () => ({comment: 0, article_ext: 0});

function failure(reason) {
  return {status: 'failed', reason, script_execution: false,
    runtime_execution_verified: false, comment_channel_verified: false};
}

function staticString(node, depth = 0) {
  if (!node || depth > 12) return null;
  if (node.type === 'Literal' && typeof node.value === 'string') {
    return node.value.length <= 2048 ? node.value : null;
  }
  if (node.type === 'TemplateLiteral' && node.expressions.length === 0) {
    const s = node.quasis[0].value.cooked;
    return typeof s === 'string' && s.length <= 2048 ? s : null;
  }
  if (node.type === 'BinaryExpression' && node.operator === '+') {
    const a = staticString(node.left, depth + 1), b = staticString(node.right, depth + 1);
    if (a !== null && b !== null && a.length + b.length <= 2048) return a + b;
  }
  return null;
}

function endpoint(node) {
  let s = staticString(node);
  if (s === null) return null;
  if (s.startsWith('https://')) {
    try {
      const u = new URL(s);
      if (u.origin !== 'https://mp.weixin.qq.com' || u.username || u.password) return null;
      s = u.pathname;
    } catch { return null; }
  } else s = s.split(/[?#]/, 1)[0];
  return Object.hasOwn(endpoints, s) ? endpoints[s] : null;
}

function memberName(node) {
  if (!node || node.type !== 'MemberExpression') return null;
  return node.computed ? staticString(node.property) : node.property.name;
}

function inspect(scripts) {
  if (!Array.isArray(scripts) || scripts.length > 128) return failure('input_rejected');
  let bytes = 0;
  for (const s of scripts) {
    if (!s || Object.keys(s).some(k => !['source', 'source_type'].includes(k)) ||
        typeof s.source !== 'string' || !['script', 'module'].includes(s.source_type)) {
      return failure('input_rejected');
    }
    bytes += Buffer.byteLength(s.source, 'utf8');
    if (bytes > SOURCE_LIMIT) return failure('source_limit');
  }
  const out = {status: 'passed', reason: 'analysis_complete', scripts_total: scripts.length,
    scripts_parsed: 0, scripts_failed: 0, nodes_visited: 0,
    endpoint_literal_nodes: pair(), endpoint_static_expressions: pair(),
    endpoint_call_argument_candidates: pair(), fetch_endpoint_candidates: pair(),
    ajax_url_candidates: pair(), dynamic_fetch_candidates: 0, dynamic_ajax_url_candidates: 0,
    bridge_invoke_candidates: 0, dynamic_bridge_method_candidates: 0,
    script_execution: false, runtime_execution_verified: false, comment_channel_verified: false};
  for (const s of scripts) {
    let tree;
    try { tree = parse(s.source, {ecmaVersion: 'latest', sourceType: s.source_type}); }
    catch (e) {
      // Acorn 8.19 converts engine stack exhaustion into this fixed SyntaxError.
      if (!(e instanceof SyntaxError) ||
          e.message.startsWith('Not enough stack space to parse input (')) {
        return failure('parser_resource_failure');
      }
      out.scripts_failed++; out.status = 'partial'; out.reason = 'syntax_incomplete';
      continue;
    }
    out.scripts_parsed++;
    const stack = [tree];
    while (stack.length) {
      const node = stack.pop();
      if (++out.nodes_visited > NODE_LIMIT) return failure('node_limit');
      const ep = endpoint(node);
      if (ep && node.type === 'Literal') out.endpoint_literal_nodes[ep]++;
      if (ep && ['BinaryExpression', 'TemplateLiteral'].includes(node.type)) {
        out.endpoint_static_expressions[ep]++;
      }
      if (node.type === 'CallExpression') {
        for (const arg of node.arguments) {
          const found = endpoint(arg);
          if (found) out.endpoint_call_argument_candidates[found]++;
        }
        const callee = node.callee;
        if (callee.type === 'Identifier' && callee.name === 'fetch') {
          const found = endpoint(node.arguments[0]);
          if (found) out.fetch_endpoint_candidates[found]++;
          else if (staticString(node.arguments[0]) === null) out.dynamic_fetch_candidates++;
        }
        const name = callee.type === 'Identifier' ? callee.name : memberName(callee);
        if (name === 'ajax') {
          const options = node.arguments[0];
          if (options?.type === 'ObjectExpression') {
            // Spreads, computed keys, duplicates or accessors make the effective URL unknown.
            const rows = options.properties;
            const uncertain = rows.some(p => p.type !== 'Property' || p.computed || p.kind !== 'init');
            const urls = rows.filter(p => p.type === 'Property' &&
              (p.key.name === 'url' || p.key.value === 'url'));
            if (uncertain || urls.length > 1) out.dynamic_ajax_url_candidates++;
            else if (urls.length === 1) {
              const found = endpoint(urls[0].value);
              if (found) out.ajax_url_candidates[found]++;
              else if (staticString(urls[0].value) === null) out.dynamic_ajax_url_candidates++;
            }
          } else out.dynamic_ajax_url_candidates++;
        }
        if (memberName(callee) === 'invoke' && callee.object?.type === 'Identifier' &&
            callee.object.name === 'WeixinJSBridge') {
          out.bridge_invoke_candidates++;
          if (staticString(node.arguments[0]) === null) out.dynamic_bridge_method_candidates++;
        }
      }
      for (const value of Object.values(node)) {
        if (Array.isArray(value)) {
          for (const child of value) if (child && typeof child.type === 'string') stack.push(child);
        } else if (value && typeof value.type === 'string') stack.push(value);
      }
    }
  }
  return out;
}

let result;
try {
  const chunks = [], buffer = Buffer.alloc(65536);
  let total = 0, read;
  while ((read = fs.readSync(0, buffer, 0, buffer.length, null)) > 0) {
    total += read;
    if (total > INPUT_LIMIT) throw new RangeError();
    chunks.push(Buffer.from(buffer.subarray(0, read)));
  }
  const input = new TextDecoder('utf-8', {fatal: true}).decode(Buffer.concat(chunks));
  result = inspect(JSON.parse(input));
} catch (e) { result = failure(e instanceof RangeError ? 'input_limit' : 'input_rejected'); }
process.stdout.write(JSON.stringify(result) + '\n');
process.exitCode = result.status === 'passed' ? 0 : 2;
