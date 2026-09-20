// Table names are SQL identifiers made from file names (salary_register_2025_register). The
// analyst never chose them and should not have to read them: everywhere outside the SQL itself a
// table is called by the file, and the sheet, it came from.
//
// Only `import type` here: the tests load this file directly with `node --test`.

import type { Answer, ClarifyOption, TableProfile } from '../types'

type Named = Pick<TableProfile, 'name' | 'source_file' | 'sheet'>

/** The file name; the sheet is added only when the same workbook gave more than one table. */
export function tableLabel(table: Named, tables: Named[]): string {
  const manySheets = tables.filter((t) => t.source_file === table.source_file).length > 1
  return table.sheet && manySheets ? `${table.source_file} (sheet ${table.sheet})` : table.source_file
}

/** A SQL table name in the analyst's words. A name that is not loaded any more is shown as it is. */
export function labelOf(name: string, tables: Named[]): string {
  const table = tables.find((t) => t.name === name)
  return table ? tableLabel(table, tables) : name
}

/**
 * Swaps SQL table names inside a sentence written by the server (a caveat, a confidence reason)
 * for file names. Two limits keep it from damaging plain English: only names with an underscore
 * or a digit are swapped (`employees` and `sales` are also ordinary words, and "total sales" must
 * not become "total sales.csv"), and a `table.column` reference is left whole.
 */
export function plainTables(text: string, tables: Named[]): string {
  const names = tables.map((t) => t.name).filter((name) => /[_\d]/.test(name))
  if (names.length === 0) return text
  const escaped = names.map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  return text.replace(new RegExp(`(?<![\\w.])(?:${escaped.join('|')})(?!\\w|\\.\\w)`, 'g'), (name) => labelOf(name, tables))
}

/**
 * The two pieces of prose a saved answer still shows on the board, with table names already
 * swapped for file names. The board renders from the project record with no catalog loaded (§6.5),
 * so a caveat resolved only at render time would print "salary_register" on the one page that
 * leaves the app. Doing it once, as the turn is stored, is what `tableLabel` would have done
 * anyway, and running it twice changes nothing — a file name matches no table name.
 *
 * The technical name is not lost: How I got this still shows the SQL and the tables it read (§8).
 */
export function plainAnswer(answer: Answer, tables: Named[]): Answer {
  const caveats = answer.work.caveats.map((caveat) => plainTables(caveat, tables))
  const cross_check = { ...answer.work.cross_check, detail: plainTables(answer.work.cross_check.detail, tables) }
  return { ...answer, work: { ...answer.work, caveats, cross_check } }
}

/**
 * The same swap for a computed tile (§13, §14). Done once, where the tile arrives from the
 * server, for the same reason as `plainAnswer`: a tile saved to the board is re-read on a page
 * that has no catalog loaded, and "removed from salary_register_2025_register" is not a sentence
 * anyone wants to print. The SQL in "View table and SQL" still names the real tables.
 */
export function plainTile<T extends { statement: string; caveats: string[] }>(tile: T, tables: Named[]): T {
  return { ...tile, statement: plainTables(tile.statement, tables), caveats: tile.caveats.map((caveat) => plainTables(caveat, tables)) }
}

/** "employees.ctc" -> "ctc in employees.csv", using the header as it is written in the file. */
export function columnLabel(ref: string, tables: TableProfile[]): string {
  const dot = ref.indexOf('.')
  const table = tables.find((t) => t.name === ref.slice(0, dot))
  const column = table?.columns.find((c) => c.name === ref.slice(dot + 1))
  return table && column ? `${column.label} in ${tableLabel(table, tables)}` : ref
}

/**
 * The text on a "which one did you mean?" chip. The server writes "Gross pay (salary_register.gross)";
 * the analyst reads "Gross pay — Gross in Salary_Register.xlsx". When the server's words are just
 * the column name again ("ctc (employees.ctc)") they are not repeated.
 *
 * An em dash, not a middle dot: a middle dot is the house style of generated interfaces, and the
 * two halves here are a meaning and where it lives, which is a sentence break.
 */
export function optionLabel(option: ClarifyOption, tables: TableProfile[]): string {
  const where = columnLabel(option.value, tables)
  if (where === option.value) return option.label
  const meaning = option.label.replace(/\s*\([^()]*\)\s*$/, '')
  return where.toLowerCase().startsWith(`${meaning.toLowerCase()} in `) ? where : `${meaning} — ${where}`
}
