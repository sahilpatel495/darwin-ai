// `#/welcome` (§7): three steps, once, with a way out of every one of them.
//
// The old product opened a six-step coach-mark tour over a screen the analyst had not used yet.
// This asks for two things it will actually use — what to call you and what you do, which tunes
// the suggested questions — then gets files in, then shows what it did with them. Step three is
// the only part that teaches, and it teaches by reporting rather than by explaining.
//
// "Skip for now" is on every step and does the same thing everywhere: mark onboarding done and
// leave. A step someone can only escape by finishing it is not skippable.

import { useState } from 'react'
import { ROLES } from '../../lib/suggestions'
import type { Catalog, User } from '../../types'
import type { SessionActions } from '../auth/session-actions'
import { AuroraBackdrop } from '../graphics'
import { NOTHING_READ, problemFrom } from '../shell/problem'
import type { Problem } from '../shell/problem'
import { Banner, Button, Chip, Input, ProgressRing } from '../ui'
import SampleFilesDialog from '../home/SampleFilesDialog'
import DropZone from '../upload/DropZone'
import UploadProgress from '../upload/UploadProgress'
import type { Busy } from '../upload/UploadProgress'
import { checkFiles } from '../upload/files'
import ReadingFiles from './ReadingFiles'

export type LoadSource = { kind: 'sample' } | { kind: 'files'; files: File[] }

export interface WelcomeProps {
  user: User | null
  session: SessionActions
  /** Files this reader already has, when they reached onboarding with a project open. */
  catalog?: Catalog | null
  /** Creates the project and resolves with what was read. The app owns project records. */
  onLoad: (source: LoadSource) => Promise<Catalog>
  /** Asks a question in the new project. */
  onAsk: (question: string) => void
  /** Opens the new project's Overview. */
  onOverview: () => void
  /** Leaves onboarding without finishing it. Called after `onboarded` has been recorded. */
  onSkip: () => void
}

const STEPS = 3

export default function Welcome({ user, session, catalog: loaded, onLoad, onAsk, onOverview, onSkip }: WelcomeProps) {
  const [step, setStep] = useState(loaded ? 3 : 1)
  const [name, setName] = useState(user?.name && user.name !== 'Guest' ? user.name : '')
  const [role, setRole] = useState<string | null>(user?.role ?? null)
  const [catalog, setCatalog] = useState<Catalog | null>(loaded ?? null)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [showingSample, setShowingSample] = useState(false)

  /** Never allowed to fail loudly: a server without accounts must not trap anyone on this screen. */
  const remember = (patch: { name?: string; role?: string | null; onboarded?: boolean }) =>
    session.updateProfile(patch).catch(() => undefined)

  function finishStepOne() {
    void remember({ name: name.trim() || undefined, role })
    setStep(2)
  }

  function skip() {
    void remember({ onboarded: true })
    onSkip()
  }

  async function load(source: LoadSource) {
    setProblem(null)
    setBusy(source.kind === 'sample' ? { kind: 'sample' } : { kind: 'upload', files: source.files.length, fraction: 0 })
    try {
      const read = await onLoad(source)
      if (!read?.tables?.length) return setProblem(NOTHING_READ)
      setCatalog(read)
      setStep(3)
    } catch (error) {
      setProblem(problemFrom(error))
    } finally {
      setBusy(null)
    }
  }

  function onFiles(picked: File[]) {
    const { accepted, problems } = checkFiles(picked)
    if (problems.length) setProblem({ message: problems.join('\n'), nextStep: '', tone: 'warn' })
    if (accepted.length) void load({ kind: 'files', files: accepted })
  }

  return (
    <div className="relative isolate min-h-full">
      <AuroraBackdrop intensity="panel" />

      <div className="relative mx-auto w-full max-w-[52rem] px-4 py-10 sm:px-6 sm:py-14">
        {/* Step three draws a ring of its own while it reads the files, and two rings filling at
            once — one of them already full — is a header arguing with the page under it. The step
            counter stands down and leaves the way out. */}
        <div className="flex items-center justify-between gap-4">
          {step < STEPS ? (
            <ProgressRing value={step / STEPS} size={48} label="Setting up DarwinLens">
              {step}/{STEPS}
            </ProgressRing>
          ) : (
            <span />
          )}
          <Button variant="quiet" onClick={skip}>
            Skip for now
          </Button>
        </div>

        <div className="mt-10">
          {step === 1 && (
            <section>
              <h1 className="text-display-lg text-ink-deep">What should we call you?</h1>
              <p className="mt-4 measure text-subtitle-md text-slate">
                Your name goes on the greeting, and what you do decides which questions DarwinLens offers you first.
                Both can be changed in Settings.
              </p>

              <form
                className="mt-9 max-w-[26rem]"
                onSubmit={(event) => {
                  event.preventDefault()
                  finishStepOne()
                }}
              >
                <Input label="Your name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" autoFocus />

                <fieldset className="mt-7">
                  <legend className="text-body-sm font-bold text-ink-deep">What do you do?</legend>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {ROLES.map((option) => (
                      <Chip key={option} selected={role === option} onClick={() => setRole((was) => (was === option ? null : option))}>
                        {option}
                      </Chip>
                    ))}
                  </div>
                </fieldset>

                <Button type="submit" variant="action" className="mt-9">
                  Continue
                </Button>
              </form>
            </section>
          )}

          {step === 2 && (
            <section>
              <h1 className="text-display-lg text-ink-deep">Bring your data</h1>
              <p className="mt-4 measure text-subtitle-md text-slate">
                Exports straight out of your HR system are the point — title rows, total rows, ₹ symbols and all. Or
                use a made-up company and bring your own files later.
              </p>

              <div className="mt-9 max-w-[32rem]">
                {busy ? (
                  <UploadProgress busy={busy} />
                ) : (
                  <>
                    <DropZone onFiles={onFiles} />
                    <div className="mt-5 flex flex-wrap items-center gap-3">
                      <Button variant="primary" onClick={() => void load({ kind: 'sample' })}>
                        Use the sample company
                      </Button>
                      <Button variant="ghost" onClick={() => setShowingSample(true)}>
                        See what’s inside
                      </Button>
                    </div>
                    {/* The real contents of demo_data/: anything shorter reads as a promise the
                        file list two screens later does not keep. */}
                    <p className="mt-3 text-body-sm text-steel">
                      500 employees, a payroll register, two attendance exports, performance reviews and a sales export.
                    </p>
                  </>
                )}
              </div>

              {problem && (
                <Banner tone={problem.tone} nextStep={problem.nextStep} onDismiss={() => setProblem(null)} className="mt-6 max-w-[32rem]">
                  {problem.message}
                </Banner>
              )}

              <SampleFilesDialog
                open={showingSample}
                onClose={() => setShowingSample(false)}
                onLoad={() => void load({ kind: 'sample' })}
                busy={busy !== null}
              />
            </section>
          )}

          {step === 3 && catalog && (
            <ReadingFiles
              catalog={catalog}
              onAsk={onAsk}
              onOverview={onOverview}
              onReady={() => void remember({ onboarded: true })}
            />
          )}
        </div>
      </div>
    </div>
  )
}
