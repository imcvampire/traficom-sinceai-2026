export type CsvCell = string | number | boolean | null | undefined

/** Spreadsheets evaluate a text cell starting with one of these as a formula. */
const FORMULA_START = /^[=+\-@\t\r]/

function cell(value: CsvCell): string {
  if (value == null) return ''
  if (typeof value !== 'string') return String(value)
  const text = FORMULA_START.test(value) ? `'${value}` : value
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

/** RFC 4180 CSV with CRLF line ends and a UTF-8 BOM, so Excel reads non-ASCII text correctly. */
export function toCsv(header: string[], rows: CsvCell[][]): string {
  return '﻿' + [header, ...rows].map((row) => row.map(cell).join(',')).join('\r\n') + '\r\n'
}
