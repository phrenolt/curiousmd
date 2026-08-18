(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.CuriousMDLogic = api;
})(typeof window !== 'undefined' ? window : globalThis, function() {
  const shortcuts = new Map([
    ['show-shortcuts', Object.freeze({
      key: '?', keys: '?', description: 'Show this shortcuts list'
    })],
    ['focus-search', Object.freeze({
      keys: 'Ctrl/⌘ + F', description: 'Focus document search'
    })],
    ['focus-search-slash', Object.freeze({
      keys: '/', description: 'Focus search when not typing'
    })],
    ['next-match', Object.freeze({
      keys: 'Enter or F3', description: 'Go to the next search result'
    })],
    ['previous-match', Object.freeze({
      keys: 'Shift + Enter or Shift + F3', description: 'Go to the previous search result'
    })],
    ['save', Object.freeze({
      keys: 'Ctrl/⌘ + S', description: 'Save while editing'
    })],
    ['escape', Object.freeze({
      keys: 'Escape', description: 'Close a menu, clear search, or leave edit mode'
    })],
    ['indent', Object.freeze({
      keys: 'Tab', description: 'Insert two spaces in the Markdown editor'
    })],
    ['navigate', Object.freeze({
      keys: 'Ctrl + right-click', description: 'Open Navigate from the preview'
    })]
  ]);

  const supportedHtmlTags = new Set([
    'a', 'b', 'br', 'del', 'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'i', 'img', 'p', 'span', 'strong', 'sub', 'sup', 'table', 'tbody', 'td',
    'th', 'thead', 'tr'
  ]);

  function literalPattern(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function findTextMatches(text, query) {
    if (!query) return [];
    const matches = [];
    const pattern = new RegExp(literalPattern(query), 'giu');
    for (const match of text.matchAll(pattern)) {
      matches.push({start: match.index, end: match.index + match[0].length});
    }
    return matches;
  }

  function markdownVisibleMap(source) {
    let text = '';
    const offsets = [];

    function append(start, end) {
      text += source.slice(start, end);
      for (let index = start; index < end; index += 1) offsets.push(index);
    }

    function closingParen(start) {
      let depth = 1;
      for (let index = start; index < source.length; index += 1) {
        if (source[index] === '\\') {
          index += 1;
        } else if (source[index] === '(') {
          depth += 1;
        } else if (source[index] === ')') {
          depth -= 1;
          if (!depth) return index;
        }
      }
      return -1;
    }

    let index = 0;
    while (index < source.length) {
      if (source[index] === '\\' && index + 1 < source.length) {
        append(index + 1, index + 2);
        index += 2;
        continue;
      }

      if (source.startsWith('![', index)) {
        const labelEnd = source.indexOf('](', index + 2);
        if (labelEnd !== -1) {
          const destinationEnd = closingParen(labelEnd + 2);
          if (destinationEnd !== -1) {
            index = destinationEnd + 1;
            continue;
          }
        }
      }

      if (source[index] === '[') {
        const labelEnd = source.indexOf('](', index + 1);
        if (labelEnd !== -1) {
          const destinationEnd = closingParen(labelEnd + 2);
          if (destinationEnd !== -1) {
            append(index + 1, labelEnd);
            index = destinationEnd + 1;
            continue;
          }
        }
      }

      if (source[index] === '<') {
        const tagEnd = source.indexOf('>', index + 1);
        if (tagEnd !== -1) {
          const raw = source.slice(index, tagEnd + 1);
          const autolink = raw.match(/^<((?:https?|mailto):[^>\s]+)>$/i);
          if (autolink) {
            append(index + 1, tagEnd);
            index = tagEnd + 1;
            continue;
          }
          const tag = raw.match(/^<\/?\s*([a-z][a-z0-9-]*)\b[^>]*>$/i);
          if (tag && supportedHtmlTags.has(tag[1].toLowerCase())) {
            index = tagEnd + 1;
            continue;
          }
        }
      }

      const lineStart = index === 0 || source[index - 1] === '\n';
      if (lineStart && source.startsWith('```', index)) {
        const lineEnd = source.indexOf('\n', index);
        index = lineEnd === -1 ? source.length : lineEnd + 1;
        continue;
      }

      append(index, index + 1);
      index += 1;
    }
    return {text, offsets};
  }

  function offsetForLine(text, line) {
    if (line <= 1) return 0;
    let offset = 0;
    for (let current = 1; current < line; current += 1) {
      const newline = text.indexOf('\n', offset);
      if (newline === -1) return text.length;
      offset = newline + 1;
    }
    return offset;
  }

  function sourceSelection(source, target) {
    const blockStart = offsetForLine(source, target.line);
    const blockEnd = target.nextLine
      ? offsetForLine(source, target.nextLine)
      : source.length;
    let start = blockStart;
    let end = source.indexOf('\n', blockStart);
    if (end === -1 || end > blockEnd) end = blockEnd;

    if (!target.hint) return {start, end};
    const visible = markdownVisibleMap(source.slice(blockStart, blockEnd));
    const visibleMatches = findTextMatches(visible.text, target.hint.word);
    const visibleMatch = visibleMatches[target.hint.occurrence - 1];
    if (visibleMatch) {
      const mappedStart = visible.offsets[visibleMatch.start];
      const mappedEnd = visible.offsets[visibleMatch.end - 1];
      if (mappedStart !== undefined && mappedEnd !== undefined) {
        return {start: blockStart + mappedStart, end: blockStart + mappedEnd + 1};
      }
    }

    const candidates = findTextMatches(source, target.hint.word);
    if (!candidates.length) return {start, end};
    const nearest = candidates.reduce((best, current) =>
      Math.abs(current.start - blockStart) < Math.abs(best.start - blockStart) ? current : best
    );
    return nearest;
  }

  return {shortcuts, findTextMatches, markdownVisibleMap, offsetForLine, sourceSelection};
});
