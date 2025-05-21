// src/index.d.ts

// This file can be used for global type declarations or module declarations.

// If TypeScript is having trouble resolving aliased paths for shadcn/ui components
// despite tsconfig.json and vite.config.ts being set up, you could add wildcards.
// However, this is often a sign of a deeper configuration issue or TS server needing a restart.

// Example to help with module resolution if TS server is struggling with aliases:
declare module "@/components/ui/button";
declare module "@/components/ui/badge";
declare module "@/components/ui/table";
declare module "@/components/ui/drawer";
declare module "@/components/ui/sonner";
declare module "@/lib/utils";

// Or more broadly, though less safe:
// declare module "@/components/ui/*";
// declare module "@/lib/*";

// It's generally better to ensure tsconfig paths and vite aliases are correctly picked up. 