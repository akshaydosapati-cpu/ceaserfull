const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')

const { resolveAppUrl } = require('./app-shell')

test('resolveAppUrl ignores obsolete app.ceaser.ai URL', () => {
  const previous = process.env.CEASER_APP_URL
  process.env.CEASER_APP_URL = 'https://app.ceaser.ai'
  try {
    assert.equal(resolveAppUrl({ getEnv: () => 'https://app.ceaser.ai' }), 'https://heyceaser.in/console')
  } finally {
    if (previous === undefined) delete process.env.CEASER_APP_URL
    else process.env.CEASER_APP_URL = previous
  }
})

test('resolveAppUrl falls back to the local desktop app entry when present', () => {
  const localEntry = path.join(__dirname, '..', '..', '..', 'frontend', 'out', 'index.html')
  fs.mkdirSync(path.dirname(localEntry), { recursive: true })
  fs.writeFileSync(localEntry, '<html></html>')
  try {
    const result = resolveAppUrl({ getEnv: () => '' })
    assert.equal(result, pathToFileURL(localEntry).toString())
  } finally {
    fs.rmSync(localEntry, { force: true })
  }
})
