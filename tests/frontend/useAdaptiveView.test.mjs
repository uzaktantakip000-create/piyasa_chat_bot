import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getInitialMode,
  persistViewPreference,
  isValidMode,
  isCardView,
  isTableView
} from '../../useAdaptiveView.js';

class MemoryStorage {
  #store = new Map();

  getItem(key) {
    return this.#store.has(key) ? this.#store.get(key) : null;
  }

  setItem(key, value) {
    this.#store.set(key, String(value));
  }

  clear() {
    this.#store.clear();
  }
}

function withWindow(callback) {
  const previous = globalThis.window;
  const storage = new MemoryStorage();
  globalThis.window = {
    localStorage: storage,
  };
  try {
    callback(storage);
  } finally {
    globalThis.window = previous;
  }
}

test('getInitialMode falls back to default when window is missing', () => {
  assert.equal(getInitialMode('piyasa.view.test', 'cards'), 'cards');
});

test('getInitialMode reads persisted value when available', () => {
  withWindow((storage) => {
    storage.setItem('piyasa.view.test', JSON.stringify('table'));
    assert.equal(getInitialMode('piyasa.view.test', 'cards'), 'table');
  });
});

test('getInitialMode ignores invalid stored values', () => {
  withWindow((storage) => {
    storage.setItem('piyasa.view.test', JSON.stringify('grid'));
    assert.equal(getInitialMode('piyasa.view.test', 'cards'), 'cards');
  });
});

test('persistViewPreference writes valid modes and skips invalid values', () => {
  withWindow((storage) => {
    persistViewPreference('piyasa.view.test', 'table');
    assert.equal(storage.getItem('piyasa.view.test'), JSON.stringify('table'));

    persistViewPreference('piyasa.view.test', 'grid');
    assert.equal(storage.getItem('piyasa.view.test'), JSON.stringify('table'));
  });
});

test('persistViewPreference no-ops when window missing', () => {
  assert.doesNotThrow(() => {
    persistViewPreference('piyasa.view.test', 'table');
  });
});

test('isValidMode recognises supported view modes', () => {
  assert.equal(isValidMode('cards'), true);
  assert.equal(isValidMode('table'), true);
  assert.equal(isValidMode('grid'), false);
});

test('isCardView and isTableView helpers flag active view', () => {
  assert.equal(isCardView('cards'), true);
  assert.equal(isTableView('cards'), false);
  assert.equal(isTableView('table'), true);
  assert.equal(isCardView('table'), false);
});
