// Every word on the landing page, in one file.
//
// Marketing copy is the easiest part of a product to let drift: the feature card promises one
// thing, the FAQ hedges it, and the Trust page quietly contradicts both. Holding it here means
// copy.test.mjs can read all of it at once and check the two rules that matter — the analyst's
// vocabulary (§12) and no shouting — and it means changing a claim is one edit rather than a
// search. No runtime imports, so the test loads this file directly.

import type { GlyphName } from '../graphics/Glyph'

export interface Feature {
  glyph: GlyphName
  title: string
  body: string
}

/** The three-up under the hero (§7). Their titles are the product's three promises, in order. */
export const FEATURES: Feature[] = [
  {
    glyph: 'table',
    title: 'Messy files, read properly',
    body: 'Title rows above the header, a total row at the bottom, ₹ symbols inside the numbers, three date formats in one column. DarwinLens sorts all of it out as it reads, and writes down every change it made.',
  },
  {
    glyph: 'bars',
    title: 'Every number computed, not generated',
    body: 'The AI writes a query and words the result. A database runs that query over your own files and produces the figure, so there is no number in the answer that nothing computed.',
  },
  {
    glyph: 'lock',
    title: 'Your rows never reach the AI',
    body: 'It is told your columns hold a ₹ amount called Gross Pay and a date called Joining Date. It is never told what any of them say, and personal-data columns are held back entirely.',
  },
]

export interface FlowStep {
  /** The short name on the card. */
  label: string
  /** What actually happens at that point, in one line. */
  detail: string
  /** True where a model is involved, which is what the showcase card is really showing. */
  ai: boolean
}

/** The dark "See the working" card (§7): one question, end to end. A real sequence, so it is numbered. */
export const FLOW: FlowStep[] = [
  { label: 'Your question', detail: '“What did we spend on salaries last year?”', ai: false },
  { label: 'A query is written', detail: 'A model turns the question into one database query. It sees your column names, not your rows.', ai: true },
  { label: 'The query is checked', detail: 'Read-only, no hidden columns, nothing that would count the same person twice. A query that fails is rewritten, not run.', ai: false },
  { label: 'A database computes it', detail: 'The query runs over your files, here. Every figure in the answer comes out of this step.', ai: false },
  { label: 'A second model agrees', detail: 'A different model writes its own query for the same question. The answer says whether the two matched.', ai: true },
  { label: 'The answer, with its working', detail: 'The figure, the checks that passed, the chart, and everything above it kept so you can read it back.', ai: false },
]

/** "How it works" (§7): three steps, in the order they happen to an analyst. */
export const HOW_IT_WORKS: [string, string][] = [
  ['Add the exports you already have', 'Drop in .csv, .tsv, .xlsx or .xlsm files straight out of your HR system. Nothing needs tidying first.'],
  ['Ask the way you would ask a colleague', 'Plain English. When a word could mean two different columns, DarwinLens asks which one you meant instead of guessing.'],
  ['Check the working before you quote it', 'Every answer opens to show the question as it was read, the query that ran, and exactly what the AI was told.'],
]

export interface Faq {
  id: string
  question: string
  /** Paragraphs. Two at most: a third means the answer belongs on the How page. */
  answer: string[]
}

export const FAQ: Faq[] = [
  {
    id: 'privacy',
    question: 'What does the AI actually see?',
    answer: [
      'Your column names and what kind of value each one holds, how many rows a file has, the earliest and latest date in it, and short lists of repeated labels such as Bengaluru or Engineering. Not one row, not one name, not one salary. Columns holding email addresses, phone numbers, PAN, Aadhaar or bank details are held back from that description entirely.',
      'Your files themselves stay in memory on the server while you work and are dropped two hours after you stop, or the moment you press “Delete my data”. Your projects, your questions and anything you saved live in this browser and nowhere else.',
    ],
  },
  {
    id: 'models',
    question: 'Which models does it use?',
    answer: [
      'Open-weight models, and the one currently writing queries is named at the top of the Trust page alongside the others it was measured against. It was chosen by that accuracy test, not by reputation.',
      'A second, different model writes its own query for every question as a check. When the two disagree the answer tells you so and drops its own confidence rating.',
    ],
  },
  {
    id: 'files',
    question: 'What kind of files can I bring?',
    answer: [
      'CSV, TSV and Excel workbooks — .csv, .tsv, .xlsx and .xlsm — up to 50 MB and ten files at a time. Several files that describe the same people are better than one: DarwinLens finds the column they share and can then count pay from one file against headcount from another.',
    ],
  },
  {
    id: 'limits',
    question: 'How much can I ask?',
    answer: [
      'There is a cap on questions per hour and per day, and Settings shows how much of it you have used. It exists because the models run on a free allowance, not to sell you more.',
      'The Overview and Analyses tabs are not capped at all. Neither of them asks a model anything — they are computed straight from your files.',
    ],
  },
  {
    id: 'cost',
    question: 'What does it cost?',
    answer: [
      'Nothing. DarwinLens is an independent prototype built for a job assignment, so there is no plan to buy, no card to add and no trial to run out.',
    ],
  },
]

/** The footer's required line (CLAUDE.md, §0). It is not a disclaimer to bury. */
export const DISCLAIMER = 'Independent prototype for the Darwinbox FDE assignment. Not affiliated with or endorsed by Darwinbox.'

export const TAGLINE = 'See your HR data clearly. Verify every answer.'
