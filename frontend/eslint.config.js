import antfu from '@antfu/eslint-config'

export default antfu({
  vue: true,
  typescript: true,
  formatters: true,
  rules: {
    'style/max-statements-per-line': 'off',
  },
})
