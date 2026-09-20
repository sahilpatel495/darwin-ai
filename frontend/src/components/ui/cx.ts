/** Join class names, dropping anything falsy. The only "utility" in this folder. */
export const cx = (...parts: (string | false | null | undefined)[]): string => parts.filter(Boolean).join(' ')
