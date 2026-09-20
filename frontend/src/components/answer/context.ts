// What an answer statement needs but AnswerStatementProps (§10) deliberately does not carry:
// the file names behind SQL table names, the glossary behind a metric key, which answer is new
// enough to draw its ticks, and whether a new question can be asked at all. The Thread supplies
// all of it; the saved-answers board renders statements outside any Thread, so every field has
// a harmless default — nothing there animates and nothing there is clickable.
import { createContext, useContext } from 'react'
import type { Metric, TableProfile } from '../../types'

export interface AnswerContextValue {
  /** Loaded tables, so a SQL table name in a caveat can be shown as the file it came from (§8). */
  tables: TableProfile[]
  glossary: Metric[]
  /** The answer that has just arrived: the only one that animates (§4). */
  newAnswerId: string | null
  /** The first answer in the thread; its "How I got this" carries data-tour="working" (§10). */
  tourAnswerId: string | null
  /** False while another question runs, and while the files are not loaded: a chip that cannot
   *  start a question says so by being disabled rather than by doing nothing when clicked. */
  canAsk: boolean
}

const OUTSIDE_A_THREAD: AnswerContextValue = { tables: [], glossary: [], newAnswerId: null, tourAnswerId: null, canAsk: false }

export const AnswerContext = createContext<AnswerContextValue>(OUTSIDE_A_THREAD)

export const useAnswerContext = (): AnswerContextValue => useContext(AnswerContext)
