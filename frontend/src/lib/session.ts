// Who is using DarwinLens, in one hook (§9). Everything about accounts goes through here, so no
// screen ever calls the auth half of api.ts itself and there is one place that knows the answer to
// "are we signed in yet".
//
// Three facts decide the whole shell:
//  - `starting`  we are asking the server who this token belongs to; draw nothing that moves;
//  - `signed-out` no token: the landing, and nothing of anybody's work;
//  - `ready`     a member, a guest, or — on a server built before accounts — nobody at all.
//
// A guest is a real user with no email, so "signed in" is not the same as "has an account": the
// avatar menu offers a guest an account, the settings page invites them to make one, and nothing
// else in the product has to care which they are.

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, deleteAccount, ensureAuth, getMe, getStoredUser, getToken, login, logout, signup, updateProfile } from '../api'
import type { Usage, User } from '../types'

export type SessionStatus = 'starting' | 'signed-out' | 'ready'

export interface Session {
  user: User | null
  /** How many questions are left, from `getMe()`. Null until it has been asked. */
  usage: Usage | null
  status: SessionStatus
  /** Throws an ApiError with the server's own sentence, for the form to show. */
  signIn: (email: string, password: string) => Promise<void>
  /** Sent with a guest's token, this upgrades that guest: their projects stay where they are. */
  signUp: (body: { email: string; password: string; name: string; role?: string | null }) => Promise<void>
  /** On a server without accounts nobody is signed in, and everything works the same way. */
  continueAsGuest: () => Promise<void>
  signOut: () => Promise<void>
  updateProfile: (patch: { name?: string; role?: string | null; onboarded?: boolean }) => Promise<void>
  /** After an answer, because asking one is what spends the allowance. */
  refreshUsage: () => void
  /** Deletes the account on the server and forgets it here. Projects are the caller's to clear. */
  deleteEverything: () => Promise<void>
}

export function useSession(): Session {
  const [user, setUser] = useState<User | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [status, setStatus] = useState<SessionStatus>('starting')
  // Set once the component is gone, so a slow reply never sets state into nothing.
  const live = useRef(true)
  useEffect(() => {
    live.current = true
    return () => {
      live.current = false
    }
  }, [])

  const adopt = useCallback((next: User | null) => {
    setUser(next)
    setStatus('ready')
  }, [])

  const refreshUsage = useCallback(() => {
    if (!getToken()) return
    void getMe()
      .then((me) => {
        if (!live.current) return
        setUsage(me.usage)
        setUser(me.user)
      })
      .catch(() => {
        /* the allowance is a courtesy; failing to read it must not interrupt anything */
      })
  }, [])

  // On start: no token means a visitor, and a visitor sees the landing rather than a guest account
  // minted behind their back. With a token we ask the server who it belongs to, which is also how
  // the allowance arrives, and how a token the server has forgotten gets thrown away.
  useEffect(() => {
    if (!getToken()) {
      setStatus('signed-out')
      return
    }
    getMe()
      .then((me) => {
        if (!live.current) return
        setUsage(me.usage)
        adopt(me.user)
      })
      .catch((error: unknown) => {
        if (!live.current) return
        const status = error instanceof ApiError ? error.status : 0
        // 404: a server built before accounts. The product works without them, with nobody signed in.
        if (status === 404) return adopt(null)
        // 401/403: the token is no good any more. Anything else (offline, a restart) keeps the
        // person where they were — their work is in this browser and does not need the server.
        if (status === 401 || status === 403) {
          void logout()
          setStatus('signed-out')
          return
        }
        adopt(getStoredUser())
      })
  }, [adopt])

  const signIn = useCallback(
    async (email: string, password: string) => {
      adopt(await login({ email, password }))
      refreshUsage()
    },
    [adopt, refreshUsage],
  )

  const signUp = useCallback(
    async (body: { email: string; password: string; name: string; role?: string | null }) => {
      adopt(await signup(body))
      refreshUsage()
    },
    [adopt, refreshUsage],
  )

  const continueAsGuest = useCallback(async () => {
    // ensureAuth answers null on a server without the accounts routes. That is not a failure: it
    // means there is nobody to be, and the product runs exactly the same way.
    adopt(await ensureAuth())
    refreshUsage()
  }, [adopt, refreshUsage])

  const signOut = useCallback(async () => {
    await logout()
    if (!live.current) return
    setUser(null)
    setUsage(null)
    setStatus('signed-out')
  }, [])

  const update = useCallback(async (patch: { name?: string; role?: string | null; onboarded?: boolean }) => {
    const next = await updateProfile(patch)
    if (live.current) setUser(next)
  }, [])

  const deleteEverything = useCallback(async () => {
    await deleteAccount()
    if (!live.current) return
    setUser(null)
    setUsage(null)
    setStatus('signed-out')
  }, [])

  return { user, usage, status, signIn, signUp, continueAsGuest, signOut, updateProfile: update, refreshUsage, deleteEverything }
}
