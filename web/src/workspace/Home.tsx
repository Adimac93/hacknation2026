import styles from "./Home.module.css";

/** Placeholder for the clerk workstation (upload, queue, panels) built in a later task. */
export function Home() {
  return (
    <main className={styles.home}>
      <h1>Cyfryzacja formularzy</h1>
      <p>Stanowisko urzędnika jest w przygotowaniu.</p>
      <p>
        <a href="/podglad">Przejdź do podglądu e-formularza</a>
      </p>
    </main>
  );
}
