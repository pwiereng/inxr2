/**
 * React Router v7 future flags, opted into across the whole app.
 *
 * Both flags change behaviour that v7 makes the default, so opting in now keeps
 * the app and its tests on one code path and silences the "React Router Future
 * Flag Warning" messages v6 logs for each un-opted flag.
 *
 * - `v7_startTransition`  — wraps router state updates in `React.startTransition`
 * - `v7_relativeSplatPath` — relative paths inside splat routes resolve against
 *   the splat's parent rather than the matched splat value
 *
 * Every router instance (the real app router in `main.tsx`, the shared test
 * render helper, and per-test `MemoryRouter`s) must use this same object so
 * tests exercise the behaviour the app actually ships.
 *
 * This is warning cleanup only — it is not the react-router v7 major upgrade.
 */
export const ROUTER_FUTURE_FLAGS = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const
