export const formatPercent = (value: number, maxDecimals: number = 2): string => {
  if (!Number.isFinite(value)) {
    return '0'
  }

  const factor = 10 ** maxDecimals
  const rounded = Math.round(value * factor) / factor
  const fixed = rounded.toFixed(maxDecimals)

  return fixed.replace(/(\.\d*?[1-9])0+$/, '$1').replace(/\.0+$/, '')
}
