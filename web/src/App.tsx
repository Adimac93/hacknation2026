import { Preview } from "./preview/Preview";
import { Home } from "./workspace/Home";

// Two routes, switched on the path; no router dependency.
export function App() {
  const path = window.location.pathname.replace(/\/+$/, "");
  return path === "/podglad" ? <Preview /> : <Home />;
}
