# Breakscale client

Next.js App Router with React, strict TypeScript, Tailwind CSS v4, and shadcn/ui.

## Start

```sh
npm ci
npm run dev
```

Open http://localhost:3000/playground for the integrated example. Add nodes, drag them, connect handles, and save/load the canvas. Saves are compressed in this browser's IndexedDB, without server syncing. The default home page remains at `/`.

## Commands

| Command                       | Purpose                                        |
| ----------------------------- | ---------------------------------------------- |
| `npm run dev`                 | Development server                             |
| `npm run build` / `npm start` | Production build / server                      |
| `npm run check`               | Formatting, lint, TypeScript, and tests        |
| `npm run lint:fix`            | Fix supported lint findings                    |
| `npm run format`              | Format files and sort Tailwind classes         |
| `npm run typecheck`           | Generate Next route types and check TypeScript |
| `npm test`                    | Run Vitest once with jsdom                     |
| `npm run test:watch`          | Watch tests                                    |
| `npm run ui:add -- dialog`    | Add another shadcn component                   |

## Package setup

| Packages                                                                 | Configuration / example                                                                                                                |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `next`, `react`, `react-dom`, `typescript`                               | App Router, root layout, strict TypeScript, `@/*` alias                                                                                |
| `@xyflow/react`                                                          | Global stylesheet in root layout; provider, controlled canvas, controls, minimap, connections in `components/workspace-playground.tsx` |
| `zustand`, `immer`                                                       | Typed canvas store with Immer middleware in `stores/workspace-store.ts`                                                                |
| `tailwindcss`, `@tailwindcss/postcss`                                    | PostCSS config and Tailwind v4 CSS-first theme in `app/globals.css`                                                                    |
| `shadcn`                                                                 | `components.json`, neutral CSS variable theme, Radix-based Button/Input/Label/Card in `components/ui`                                  |
| `lucide-react`                                                           | Form and save/load icons                                                                                                               |
| `clsx`, `tailwind-merge`                                                 | Shared `cn()` in `lib/utils.ts`                                                                                                        |
| `class-variance-authority`                                               | Typed button variants                                                                                                                  |
| `motion`                                                                 | Client animation respecting reduced-motion preferences                                                                                 |
| `react-hook-form`, `@hookform/resolvers`, `zod`                          | Accessible form in `components/node-form.tsx`; shared form/snapshot schemas in `lib/schemas/workspace.ts`                              |
| `recharts`                                                               | Responsive canvas totals chart                                                                                                         |
| `idb`, `lz-string`                                                       | Versioned IndexedDB storage, compression, validation, and connection cleanup in `lib/storage.ts`                                       |
| `nanoid`, `date-fns`                                                     | Node IDs and save timestamps                                                                                                           |
| `@google/genai`                                                          | Server-only client and `generateText()` in `lib/server/gemini.ts`                                                                      |
| `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` | Vitest config, test cleanup/matchers, form/storage tests                                                                               |
| `prettier`, `prettier-plugin-tailwindcss`                                | Prettier config with v4 stylesheet; generated files excluded                                                                           |
| `eslint`, `eslint-config-next`                                           | Flat config with Next web-vitals and TypeScript rules                                                                                  |
| `@types/node`, `@types/react`, `@types/react-dom`                        | Type definitions; Node 26 types match the development runtime                                                                          |

Supporting packages include `server-only`, the React Vite plugin, Testing Library DOM, and `fake-indexeddb` for storage tests. The original Turbopack Tailwind package remains installed; CSS uses PostCSS to avoid running two Tailwind transforms.

Import interactive libraries from client components (`"use client"`). Wrap canvases in `ReactFlowProvider` and give canvases/charts containers explicit heights. For larger components, use Zustand selectors to narrow subscriptions.

## Gemini

Copy `.env.example` to `.env.local` and set `GEMINI_API_KEY` and `GEMINI_MODEL` from your Google AI Studio account. Restart the dev server after changing them. Neither variable uses `NEXT_PUBLIC_`.

Import only from server components, actions, or route handlers:

```ts
import { generateText } from "@/lib/server/gemini";

const text = await generateText("Describe this workflow");
```

Environment validation happens when Gemini is used, so development and builds work without credentials. There is no publicly callable AI endpoint. Add application authentication and usage controls when exposing this helper through an action or route. Tests do not call Google or incur API charges.

## References

- [shadcn installation](https://ui.shadcn.com/docs/installation/manual)
- [Next.js Vitest setup](https://nextjs.org/docs/app/guides/testing/vitest)
- [Google Gen AI SDK](https://github.com/googleapis/js-genai)
