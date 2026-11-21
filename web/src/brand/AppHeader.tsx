import type { ReactNode } from "react";
import styles from "./AppHeader.module.css";
import { Logo } from "./Logo";

/** Application header: linear mark linking home, optional actions on the right. */
export function AppHeader({ children }: { children?: ReactNode }) {
  return (
    <header className={styles.header}>
      <a href="/" aria-label="Biurokratka — strona główna" className={styles.logo}>
        <Logo />
      </a>
      {children ? <div className={styles.actions}>{children}</div> : null}
    </header>
  );
}
