// Settings (§8): who you are, how many questions you have left, and the two ways out — signing
// out, and deleting everything DarwinLens holds about you.
//
// A guest gets one extra card, and it is an invitation rather than a nag: their projects already
// work, and an account is only what makes them survive this browser.

import { useState } from 'react'
import { ROLES } from '../../lib/suggestions'
import { clearProjects } from '../../lib/projects'
import { go, HOME, SIGNUP } from '../../lib/route'
import type { Session } from '../../lib/session'
import { Badge, Banner, Button, Card, Chip, Dialog, Input, UsageMeter, toast } from '../ui'
import { problemFrom } from '../shell/problem'
import type { Problem } from '../shell/problem'

export interface SettingsPageProps {
  session: Session
}

export default function SettingsPage({ session }: SettingsPageProps) {
  const { user, usage } = session
  const [name, setName] = useState(user?.name ?? '')
  const [role, setRole] = useState<string | null>(user?.role ?? null)
  const [saving, setSaving] = useState(false)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [confirming, setConfirming] = useState(false)

  const guest = user?.kind !== 'member'
  const changed = user !== null && (name.trim() !== user.name || role !== user.role)

  async function save() {
    setProblem(null)
    setSaving(true)
    try {
      await session.updateProfile({ name: name.trim(), role })
      toast('Profile saved')
    } catch (error) {
      setProblem(problemFrom(error))
    } finally {
      setSaving(false)
    }
  }

  async function deleteEverything() {
    setConfirming(false)
    setProblem(null)
    try {
      clearProjects()
      await session.deleteEverything()
      go(HOME)
    } catch (error) {
      setProblem(problemFrom(error))
    }
  }

  return (
    <main className="mx-auto w-full max-w-[820px] px-4 py-10 sm:px-6 sm:py-14">
      <h1 className="text-heading-lg text-ink-deep">Settings</h1>

      {problem && (
        <Banner tone={problem.tone} nextStep={problem.nextStep} onDismiss={() => setProblem(null)} className="mt-6">
          {problem.message}
        </Banner>
      )}

      {user === null ? (
        <p className="mt-6 measure text-body-md text-slate">
          This server does not keep accounts, so there is nothing here to change. Your projects live in this browser and nowhere else.
        </p>
      ) : (
        <div className="mt-8 space-y-6">
          <Card as="section">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-heading-sm text-ink-deep">You</h2>
              <Badge tone={guest ? 'attention' : 'success'}>{guest ? 'Guest' : 'Account'}</Badge>
            </div>

            <div className="mt-6 max-w-sm">
              <Input label="Your name" value={name} maxLength={60} onChange={(event) => setName(event.target.value)} />
              {user.email && <p className="mt-3 text-body-sm text-steel">Signed in as {user.email}</p>}
            </div>

            <fieldset className="mt-6">
              <legend className="text-body-sm font-bold text-ink-deep">What you do</legend>
              <p className="mt-1 text-body-sm text-steel">It decides which questions DarwinLens offers you first. Nothing else.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {ROLES.map((option) => (
                  <Chip key={option} selected={role === option} onClick={() => setRole(role === option ? null : option)}>
                    {option}
                  </Chip>
                ))}
              </div>
            </fieldset>

            <div className="mt-6">
              <Button variant="primary" disabled={!changed || name.trim().length === 0} loading={saving} onClick={save}>
                Save changes
              </Button>
            </div>
          </Card>

          <Card as="section">
            <h2 className="text-heading-sm text-ink-deep">Questions left</h2>
            <p className="mt-2 measure text-body-sm text-slate">
              Asking is the only thing with a limit, because it is the only thing that reaches a model. The overview and the analyses are computed from
              your files and are never counted.
            </p>
            {usage ? (
              <div className="mt-6 space-y-5">
                <UsageMeter label="This hour" used={usage.asks_this_hour} limit={usage.asks_per_hour} />
                <UsageMeter label="Today" used={usage.asks_today} limit={usage.asks_per_day} />
              </div>
            ) : (
              <p className="mt-6 text-body-sm text-steel">The count arrives with your first question of the day.</p>
            )}
          </Card>

          {guest && (
            <Card as="section" tone="soft">
              <h2 className="text-heading-sm text-ink-deep">Keep your place</h2>
              <p className="mt-2 measure text-body-sm text-slate">
                You are working as a guest, which is enough to ask anything. An account keeps the projects you have already made and lets you find them
                again from another browser.
              </p>
              <Button variant="action" className="mt-5" onClick={() => go(SIGNUP)}>
                Create an account
              </Button>
            </Card>
          )}

          <Card as="section">
            <h2 className="text-heading-sm text-ink-deep">Leaving</h2>
            <p className="mt-2 measure text-body-sm text-slate">
              Signing out leaves your projects in this browser, under your account. Deleting takes them away along with everything the server holds.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button
                variant="secondary"
                onClick={() => {
                  void session.signOut().then(() => go(HOME))
                }}
              >
                Sign out
              </Button>
              <Button variant="ghost" onClick={() => setConfirming(true)}>
                Delete my data
              </Button>
            </div>
          </Card>
        </div>
      )}

      <Dialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Delete everything?"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Keep my data
            </Button>
            <Button variant="primary" onClick={deleteEverything}>
              Delete everything
            </Button>
          </>
        }
      >
        <p>
          Every project in this browser goes, along with your account and any files still loaded on the server. The files on your own computer are not
          touched. This cannot be undone.
        </p>
      </Dialog>
    </main>
  )
}
