import { Preview } from "./preview/Preview";
import { Workspace } from "./workspace/Workspace";

// Two routes, switched on the path; no router dependency.
export function App() {
  const path = window.location.pathname.replace(/\/+$/, "");
  return path === "/podglad" ? <Preview /> : <Workspace />;
}
