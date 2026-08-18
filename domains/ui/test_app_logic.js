'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  shortcuts, findTextMatches, markdownVisibleMap, offsetForLine, sourceSelection
} = require('./app_logic.js');

test('shortcut registry contains display text and the help trigger', () => {
  assert.ok(shortcuts instanceof Map);
  assert.equal(shortcuts.get('show-shortcuts').key, '?');
  assert.equal(shortcuts.get('focus-search').keys, 'Ctrl/⌘ + F');
  for (const shortcut of shortcuts.values()) {
    assert.ok(shortcut.keys);
    assert.ok(shortcut.description);
  }
});

test('findTextMatches finds case-insensitive non-overlapping source ranges', () => {
  assert.deepEqual(findTextMatches('Gold gold GOLD', 'gold'), [
    {start: 0, end: 4},
    {start: 5, end: 9},
    {start: 10, end: 14}
  ]);
});

test('findTextMatches ignores an empty query', () => {
  assert.deepEqual(findTextMatches('anything', ''), []);
});

test('findTextMatches preserves UTF-16 offsets during case folding', () => {
  assert.deepEqual(findTextMatches('İX', 'x'), [{start: 1, end: 2}]);
});

test('markdownVisibleMap excludes link destinations', () => {
  const source = '[here](https://example.com/target) target';
  const visible = markdownVisibleMap(source);
  assert.equal(visible.text, 'here target');
  assert.equal(visible.offsets[5], source.lastIndexOf('target'));
});

test('offsetForLine resolves one-based Markdown lines', () => {
  const source = '# One\n\nSecond line\nThird line';
  assert.equal(offsetForLine(source, 1), 0);
  assert.equal(offsetForLine(source, 3), 7);
  assert.equal(offsetForLine(source, 99), source.length);
});

test('sourceSelection selects the clicked occurrence inside its block', () => {
  const source = '# Heading\n\nRepeat this, then repeat this.\n\nNext';
  assert.deepEqual(sourceSelection(source, {
    line: 3,
    nextLine: 5,
    hint: {word: 'repeat', occurrence: 2}
  }), {start: 29, end: 35});
});

test('sourceSelection falls back to the mapped source line', () => {
  const source = '# Heading\n\nA paragraph\n\nNext';
  assert.deepEqual(sourceSelection(source, {line: 3, nextLine: 5, hint: null}), {
    start: 11,
    end: 22
  });
});

test('sourceSelection falls back when line metadata is unavailable', () => {
  const source = '<h2>Navigate here</h2>';
  assert.deepEqual(sourceSelection(source, {
    line: 4,
    nextLine: null,
    hint: {word: 'Navigate', occurrence: 1}
  }), {start: 4, end: 12});
});

test('sourceSelection uses preserved raw HTML line metadata', () => {
  const source = '<p>alpha</p>\n\none\n\nalpha';
  assert.deepEqual(sourceSelection(source, {
    line: 1,
    nextLine: 3,
    hint: {word: 'alpha', occurrence: 1}
  }), {start: 3, end: 8});
});

test('sourceSelection ignores matches inside Markdown link destinations', () => {
  const source = '[here](https://example.com/target) target';
  const start = source.lastIndexOf('target');
  assert.deepEqual(sourceSelection(source, {
    line: 1,
    nextLine: null,
    hint: {word: 'target', occurrence: 1}
  }), {start, end: start + 'target'.length});
});

test('sourceSelection preserves multilingual source offsets', () => {
  assert.deepEqual(sourceSelection('İX', {
    line: 1,
    nextLine: null,
    hint: {word: 'x', occurrence: 1}
  }), {start: 1, end: 2});
});
