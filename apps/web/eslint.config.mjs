import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

const eslintConfig = [
  ...nextVitals,
  ...nextTypeScript,
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      // The knowledge base renders documents written by workspace members and
      // read by anonymous visitors. Rendering from a node table into React
      // elements is what makes that safe; one dangerouslySetInnerHTML would
      // undo it, so the rule is absolute rather than per-file.
      "react/no-danger": "error",
    },
  },
];

export default eslintConfig;
