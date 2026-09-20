// The landing page (§7). The one screen a hiring panel sees before they decide whether to press
// anything, so it has exactly one obvious thing to do: **Try the live demo** — a black pill that
// becomes a guest, loads the sample company and drops the visitor into a workspace with a question
// waiting. No form, no email, no "book a call".
//
// "Create an account" sits beside it as an outline, because somebody who already trusts the idea
// should not have to go through the demo to keep their work.
//
// Everything below the hero is evidence for that button, in descending order of how sceptical the
// reader is: what it handles, how it works, what it has scored, what it costs.

import { useEffect, useState } from 'react'
import { getEvalReport } from '../../api'
import { go, HOW, SIGNUP, TRUST } from '../../lib/route'
import type { EvalReport } from '../../types'
import type { Problem } from '../shell/problem'
import { AppPreview, AuroraBackdrop, Glyph } from '../graphics'
import { Accordion, Banner, Button, Card } from '../ui'
import { FAQ, FEATURES, HOW_IT_WORKS } from './copy'
import { MarketingFooter, MarketingNav, PromoStrip } from './MarketingChrome'
import { proofNumbers } from './proof'
import Showcase from './Showcase'

export interface LandingProps {
  /** Becomes a guest, loads the sample company and opens its workspace. One press, nothing else. */
  onTryDemo: () => void
  /** True while that is happening: the pill keeps its width and says what is going on. */
  loading?: boolean
  /** Whatever stopped it, in the app's two sentences. */
  error?: Problem | null
  onDismissError?: () => void
}

/** 80px between sections on a desktop, 64 on a phone (§2). One class, used everywhere below. */
const SECTION = 'mx-auto w-full max-w-[1200px] px-4 py-16 sm:px-6 sm:py-20'

export default function Landing({ onTryDemo, loading = false, error, onDismissError }: LandingProps) {
  // The proof row is the only thing on this page that comes off the network, and it is allowed to
  // fail: `proofNumbers(null)` still returns the facts that are true without a measurement.
  const [report, setReport] = useState<EvalReport | null>(null)
  useEffect(() => {
    let live = true
    getEvalReport()
      .then((r) => live && setReport(r))
      .catch(() => {
        /* no accuracy test has been run here; the row falls back */
      })
    return () => {
      live = false
    }
  }, [])
  const proof = proofNumbers(report)

  return (
    <div className="bg-canvas">
      <PromoStrip />
      <MarketingNav />

      <main>
        {/* --- Hero ------------------------------------------------------------------------ */}
        <section className="relative isolate overflow-hidden">
          <AuroraBackdrop intensity="hero" />
          <div className="relative mx-auto flex w-full max-w-[1200px] flex-col items-center px-4 pt-16 pb-20 text-center sm:px-6 sm:pt-24">
            <h1 className="measure text-hero-display text-ink-deep">Ask your spreadsheets. Verify every answer.</h1>
            <p className="mt-6 max-w-[46ch] text-subtitle-md text-slate">
              Bring the HR exports you already have, ask in plain English, and open any answer to see exactly how the
              number was worked out.
            </p>

            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Button variant="primary" onClick={onTryDemo} loading={loading}>
                Try the live demo
              </Button>
              <Button variant="secondary" onClick={() => go(SIGNUP)}>
                Create an account
              </Button>
            </div>
            <p className="mt-4 text-body-sm text-steel">
              No account, no upload: the demo loads a made-up company of 500 employees.
            </p>

            {error && (
              <Banner tone={error.tone} nextStep={error.nextStep} onDismiss={onDismissError} className="mt-6 max-w-xl text-left">
                {error.message}
              </Banner>
            )}

            <div className="mt-14 flex w-full justify-center">
              <AppPreview />
            </div>
            {/* Not "an answer from the sample company": the figures in the preview are illustrative
                and the sample's own totals are different, so the caption promises the drawing, not
                the data. */}
            <p className="mt-4 text-body-sm text-steel">An answer card, drawn exactly the way the product draws yours.</p>
          </div>
        </section>

        {/* --- What it handles -------------------------------------------------------------- */}
        <section className={SECTION}>
          <div className="stagger-children grid grid-cols-1 gap-4 md:grid-cols-3">
            {FEATURES.map((feature, i) => (
              <Card as="article" key={feature.title} radius="xxl">
                <Glyph
                  name={feature.glyph}
                  size={48}
                  // The middle card takes the second accent, so a row of three reads as a set
                  // rather than as one drawing repeated in three colours.
                  accent={i === 1 ? 'var(--color-purple)' : undefined}
                  className="text-charcoal"
                />
                <h2 className="mt-6 text-heading-sm text-ink-deep">{feature.title}</h2>
                <p className="mt-3 text-body-md text-slate">{feature.body}</p>
              </Card>
            ))}
          </div>
        </section>

        {/* --- See the working -------------------------------------------------------------- */}
        <section className={SECTION}>
          <Showcase />
        </section>

        {/* --- Proof ------------------------------------------------------------------------ */}
        <section className={SECTION}>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h2 className="text-display-lg text-ink-deep">Measured, not asserted</h2>
            <a href={TRUST} className="text-body-md text-primary-deep">
              Read the full trust report
            </a>
          </div>
          {/* A hairline above each figure, not a card around it: four boxes here would make the
              page one more grid of tiles, and these are statements, not objects. */}
          <ul className="mt-10 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
            {proof.map((number) => (
              <li key={number.label} className="border-t border-hairline-soft pt-5">
                <p className="text-heading-lg text-ink-deep tnum">{number.value}</p>
                <h3 className="mt-2 text-subtitle-lg text-ink-deep">{number.label}</h3>
                <p className="mt-1.5 text-body-sm text-steel">{number.note}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* --- How it works ----------------------------------------------------------------- */}
        <section className={SECTION}>
          <h2 className="text-display-lg text-ink-deep">How it works</h2>
          <ol className="mt-10 grid grid-cols-1 gap-8 md:grid-cols-3">
            {HOW_IT_WORKS.map(([title, detail], i) => (
              <li key={title}>
                {/* Numbered because this really is a sequence: the steps only make sense in order. */}
                <span className="inline-flex size-9 items-center justify-center rounded-full bg-ink-deep text-button-md text-white tnum">
                  {i + 1}
                </span>
                <h3 className="mt-5 text-heading-sm text-ink-deep">{title}</h3>
                <p className="mt-2 text-body-md text-slate">{detail}</p>
              </li>
            ))}
          </ol>
          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Button variant="primary" onClick={onTryDemo} loading={loading}>
              Try the live demo
            </Button>
            <Button variant="quiet" onClick={() => go(HOW)}>
              Read the longer version
            </Button>
          </div>
        </section>

        {/* --- Questions -------------------------------------------------------------------- */}
        <section className={SECTION}>
          <div className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-16">
            <div>
              <h2 className="text-display-lg text-ink-deep">Questions</h2>
              <p className="mt-4 text-body-md text-slate">
                The ones worth asking before you put payroll data into anything.
              </p>
            </div>
            <Accordion
              items={FAQ.map((item) => ({
                id: item.id,
                question: item.question,
                answer: item.answer.map((paragraph, i) => (
                  <p key={i} className={i === 0 ? '' : 'mt-3'}>
                    {paragraph}
                  </p>
                )),
              }))}
              defaultOpenId={FAQ[0].id}
            />
          </div>
        </section>
      </main>

      <MarketingFooter />
    </div>
  )
}
