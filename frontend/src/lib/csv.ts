// "Download CSV": a result table as a file the analyst can open in Excel. Built in the browser
// from the rows the answer already holds, so a download never costs a server call.
//
// Only `import type` here: the tests load this file directly with `node --test`.

import type { Cell } from '../types'

/**
 * One CSV field. A text cell that starts with = + - @ (or a tab or carriage return) would be run
 * as a formula by Excel and Google Sheets, and cell text comes from an uploaded file, so it may be
 * hostile (`=HYPERLINK(...)`, `@SUM(...)`). A leading single quote makes the spreadsheet show it
 * as text. Numbers are left alone: a number cannot hold a formula, and quoting -1200 would stop
 * the analyst from summing the column.
 */
function field(cell: Cell): string {
  if (cell === null) return ''
  let text = String(cell)
  if (typeof cell === 'string' && /^[=+\-@\t\r]/.test(text)) text = `'${text}`
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

/** RFC 4180: comma separated, CRLF line ends, quotes doubled. The column names are the header. */
export function toCsv(columns: string[], rows: Cell[][]): string {
  return [columns, ...rows].map((row) => row.map(field).join(',')).join('\r\n') + '\r\n'
}

/** "What was total gross pay, by dept?" -> "what-was-total-gross-pay-by-dept.csv". */
export function csvFileName(question: string): string {
  const slug = question
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, 60)
    .replace(/^-+|-+$/g, '')
  return `${slug || 'verity-result'}.csv`
}

/** Hands the file to the browser. The BOM is what makes Excel read ₹ and names as UTF-8. */
export function downloadCsv(fileName: string, csv: string): void {
  const url = URL.createObjectURL(new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000) // after the browser has started reading it
}
