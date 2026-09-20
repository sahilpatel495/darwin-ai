// Sign in and create an account (§7). One component, because they are one form with one extra
// field and one different verb — two files would drift apart by the second change.
//
// Three decisions worth stating:
//  - "Continue as guest" is always on screen, never behind a link. Somebody who came from "Try the
//    live demo" and hit this page by accident must be able to get out of it in one press.
//  - Errors are the server's own sentence. `api.ts` turns every failure into "what happened" plus
//    "what to do", so this form never writes its own wording for a 401 or a 409.
//  - Nothing is validated as you type. The browser checks the email shape on submit, the password
//    rule is stated up front, and the only other judge is the server.

import { useEffect, useState } from 'react'
import { ApiError } from '../../api'
import { HOME, SIGNIN, SIGNUP } from '../../lib/route'
import type { User } from '../../types'
import { AuroraBackdrop } from '../graphics'
import { Button, Chip, Input } from '../ui'
import { ROLES } from '../../lib/suggestions'
import type { SessionActions } from './session-actions'

/** Backend rule (`app/auth.py`): stated before it can be broken, not after. */
const MIN_PASSWORD = 8

/** The art column's line. Facts, each provable elsewhere in the product. */
const PROOF_LINES = [
  'Every figure is computed by a database from your own files.',
  'Your rows never reach the AI — only what your columns hold.',
  'A second model writes its own query and has to agree.',
  'Every answer opens to show the query that produced it.',
]

const ROTATE_MS = 6000

export interface AuthPageProps {
  mode: 'signin' | 'signup'
  session: SessionActions
  /** The current reader. A guest here is about to be upgraded, and keeps everything they have. */
  user?: User | null
  /** Signed in, signed up or continuing as a guest. The app reads the new user off `useSession()`
   *  and decides where that lands — onboarding for somebody new, their projects for everyone else. */
  onAuthed: () => void
}

/** One line at a time, changing slowly. It stands still for anyone who asked for reduced motion. */
function ProofLine() {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const timer = setInterval(() => setIndex((i) => (i + 1) % PROOF_LINES.length), ROTATE_MS)
    return () => clearInterval(timer)
  }, [])
  return (
    // aria-live, not a heading: it changes under the reader, and announcing it politely is the
    // honest thing to do with text that moves on its own.
    <p key={index} className="rise-in measure text-heading-md text-ink-deep" aria-live="polite">
      {PROOF_LINES[index]}
    </p>
  )
}

export default function AuthPage({ mode, session, user, onAuthed }: AuthPageProps) {
  const signup = mode === 'signup'
  const [name, setName] = useState(user && user.kind === 'member' ? user.name : '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [shown, setShown] = useState(false)
  const [role, setRole] = useState<string | null>(user?.role ?? null)
  const [busy, setBusy] = useState<'form' | 'guest' | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  /** Any failure the server can describe, described. Anything else is this app's bug, not theirs. */
  async function run(kind: 'form' | 'guest', work: () => Promise<void>) {
    setProblem(null)
    setBusy(kind)
    try {
      await work()
      onAuthed()
    } catch (error) {
      setProblem(
        error instanceof ApiError
          ? `${error.message} ${error.nextStep}`.trim()
          : 'Something went wrong in the app. Reload the page and try again.',
      )
      setBusy(null)
    }
  }

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (busy) return
    if (signup && password.length < MIN_PASSWORD) {
      return setProblem(`A password needs at least ${MIN_PASSWORD} characters.`)
    }
    void run('form', () =>
      signup
        ? session.signUp({ name: name.trim(), email: email.trim(), password, role })
        : session.signIn(email.trim(), password),
    )
  }

  return (
    <div className="grid min-h-full grid-cols-1 lg:grid-cols-2">
      {/* --- The form ------------------------------------------------------------------------ */}
      <div className="flex flex-col px-4 py-10 sm:px-10 sm:py-14 lg:px-16">
        <a href={HOME} className="text-heading-sm text-ink-deep no-underline">
          DarwinLens
        </a>

        <div className="mx-auto flex w-full max-w-[26rem] flex-1 flex-col justify-center py-12">
          <h1 className="text-display-lg text-ink-deep">{signup ? 'Create your account' : 'Welcome back'}</h1>
          <p className="mt-3 text-body-md text-slate">
            {signup
              ? user?.kind === 'guest'
                ? 'Everything you have already asked stays with you — the account just keeps it on this browser and any other.'
                : 'One account keeps your projects, your questions and everything you have saved.'
              : 'Sign in to find the projects you have already made.'}
          </p>

          <form onSubmit={onSubmit} className="mt-8 space-y-5">
            {signup && (
              <Input
                label="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                required
                hint="It is what the app calls you. Nothing else uses it."
              />
            )}

            <Input
              label="Work email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />

            {/* The toggle sits over the field rather than beside it, so the input keeps its full
                width at 390. Checked against ui/Field.tsx: the label block is 20px + an 8px gap, so
                the 44px input starts at 28px and its centre is 50px; a 36px `sm` button at `top-8`
                has the same centre. `pr-20` (80px) clears the ~64px pill by 10px at "Show". */}
            <div className="relative">
              <Input
                label="Password"
                type={shown ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={signup ? 'new-password' : 'current-password'}
                required
                minLength={signup ? MIN_PASSWORD : undefined}
                className="[&_input]:pr-20"
                hint={signup ? `At least ${MIN_PASSWORD} characters. Nothing else is required.` : undefined}
              />
              <Button
                variant="quiet"
                size="sm"
                onClick={() => setShown((was) => !was)}
                aria-label={shown ? 'Hide password' : 'Show password'}
                className="absolute top-8 right-1.5"
              >
                {shown ? 'Hide' : 'Show'}
              </Button>
            </div>

            {signup && (
              <fieldset>
                <legend className="text-body-sm font-bold text-ink-deep">What do you do?</legend>
                <p className="mt-1 text-body-sm text-steel">It decides which questions we suggest first. You can change it later.</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {ROLES.map((option) => (
                    <Chip key={option} selected={role === option} onClick={() => setRole((was) => (was === option ? null : option))}>
                      {option}
                    </Chip>
                  ))}
                </div>
              </fieldset>
            )}

            {problem && (
              <p role="alert" className="text-body-md text-critical">
                {problem}
              </p>
            )}

            <Button type="submit" variant="action" size="md" block loading={busy === 'form'}>
              {signup ? 'Create account' : 'Sign in'}
            </Button>
          </form>

          <p className="mt-6 text-body-md text-slate">
            {signup ? 'Already have an account? ' : 'No account yet? '}
            <a href={signup ? SIGNIN : SIGNUP}>{signup ? 'Sign in' : 'Create one'}</a>
          </p>

          <div className="mt-8 border-t border-hairline-soft pt-6">
            <Button variant="ghost" block loading={busy === 'guest'} onClick={() => void run('guest', () => session.continueAsGuest())}>
              Continue as guest
            </Button>
            <p className="mt-3 text-body-sm text-steel">
              A guest can do everything. Projects stay in this browser until you make an account.
            </p>
          </div>
        </div>
      </div>

      {/* --- The art ------------------------------------------------------------------------- */}
      {/* Stacked under the form on a phone rather than dropped (§7). The aurora is the signature
          background for auth, and a phone visitor was seeing a plain white form without it. */}
      <div className="relative isolate flex items-center overflow-hidden border-t border-hairline-soft px-4 py-12 sm:px-10 lg:border-t-0 lg:border-l lg:px-16 lg:py-0">
        <AuroraBackdrop intensity="panel" />
        <div className="relative">
          <ProofLine />
          <p className="mt-6 text-body-md text-steel">
            You can check every one of these yourself, on any answer, in two presses.
          </p>
        </div>
      </div>
    </div>
  )
}
