// The seam between the screens in this folder and the app's auth state.
//
// Narrowed rather than redeclared: these four come straight off `useSession()` (`src/lib/session.ts`,
// owned by the journey engineer), so `<AuthPage session={session} …/>` works with the real hook and
// the two files cannot drift apart. Taking the four as a prop rather than calling the hook here is
// deliberate — a sign-in form should not care whether the token lives in a React store, a module,
// or nothing at all, and it keeps these screens out of a file this owner does not own.

import type { Session } from '../../lib/session'

export type SessionActions = Pick<Session, 'signIn' | 'signUp' | 'continueAsGuest' | 'updateProfile'>
