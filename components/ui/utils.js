export function cn(...inputs) {
  const classes = []

  const push = (value) => {
    if (!value) {
      return
    }
    if (typeof value === 'string' || typeof value === 'number') {
      classes.push(String(value))
      return
    }
    if (Array.isArray(value)) {
      value.forEach((item) => push(item))
      return
    }
    if (typeof value === 'object') {
      Object.entries(value).forEach(([key, val]) => {
        if (val) {
          classes.push(key)
        }
      })
    }
  }

  inputs.forEach((input) => push(input))

  return classes.join(' ')
}
