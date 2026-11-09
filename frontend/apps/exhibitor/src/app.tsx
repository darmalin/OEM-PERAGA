import { api, ApiError, call, setCsrfToken } from "@ems/api";
import { LogOut } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { exhibitorRouteOf, href, type Me, messageOf, navigate, useRoute } from "./lib";
import { AcceptInvite } from "./pages/accept-invite";
import { ExhibitorPage } from "./pages/exhibitor";
import { Home } from "./pages/home";
import { Login } from "./pages/login";
import { OrderFormPage, OrderFormsPage, OrderReviewPage } from "./pages/order-forms";
import { Button, Notice } from "./ui";

type Session = { kind: "loading" } | { kind: "out" } | { kind: "error"; message: string } | { kind: "in"; me: Me };

export function App() {
  const { route, search } = useRoute();
  const [session, setSession] = useState<Session>({ kind: "loading" });

  const signedIn = useCallback((me: Me) => {
    setCsrfToken(me.csrf_token);
    setSession({ kind: "in", me });
  }, []);

  const load = useCallback(() => {
    call(api.GET("/api/v1/portal/auth/me"))
      .then(signedIn)
      .catch((e: unknown) => setSession(e instanceof ApiError && e.status === 401 ? { kind: "out" } : { kind: "error", message: messageOf(e) }));
  }, [signedIn]);

  useEffect(load, [load]);

  const signOut = async () => {
    try {
      await call(api.POST("/api/v1/portal/auth/logout"));
    } finally {
      setCsrfToken(null);
      setSession({ kind: "out" });
      navigate("/login", true);
    }
  };

  let body;
  if (route === "/accept-invite") {
    // Replacing the history entry drops the used token from the address bar.
    body = <AcceptInvite token={search.get("token") ?? ""} onDone={(me) => { signedIn(me); navigate("/", true); }} />;
  } else if (session.kind === "loading") {
    body = <p role="status" className="py-16 text-center text-label">Loading</p>;
  } else if (session.kind === "error") {
    body = <div className="flex flex-col items-center gap-3 py-16"><Notice>{session.message}</Notice><Button onClick={load}>Retry</Button></div>;
  } else if (session.kind === "out") {
    body = <Login onDone={(me) => { signedIn(me); if (route === "/login") navigate("/", true); }} />;
  } else if (route === "/" || route === "/login") {
    body = <Home me={session.me} />;
  } else {
    const target = exhibitorRouteOf(route);
    const record = session.me.exhibitors.find((e) => e.exhibitor_lead_id === target?.id);
    const out = () => setSession({ kind: "out" });
    if (!target || !record) body = <NotFound />;
    else if (target.page === "forms") body = <OrderFormsPage record={record} onSignedOut={out} />;
    else if (target.page === "form") body = <OrderFormPage key={target.code} record={record} code={target.code} onSignedOut={out} />;
    else if (target.page === "review") body = <OrderReviewPage key={target.code} record={record} code={target.code} onSignedOut={out} />;
    else body = <ExhibitorPage record={record} onSignedOut={out} />;
  }

  return (
    <div className="min-h-dvh">
      <header className="border-b border-line bg-bg">
        <div className="mx-auto flex h-14 max-w-[960px] items-center justify-between gap-3 px-4">
          <a href={href("/")} onClick={(e) => { e.preventDefault(); navigate("/"); }} className="rounded-[6px] text-[15px] font-semibold">Exhibitor Portal</a>
          {session.kind === "in" ? (
            <div className="flex min-w-0 items-center gap-2">
              <span className="truncate text-[13px] text-label max-sm:hidden">{session.me.email}</span>
              <Button variant="ghost" className="h-9 px-3" onClick={() => void signOut()}><LogOut aria-hidden />Sign Out</Button>
            </div>
          ) : null}
        </div>
      </header>
      <main className="mx-auto w-full max-w-[960px] px-4 py-6 sm:py-10">{body}</main>
    </div>
  );
}

function NotFound() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <p className="text-[16px] font-semibold">This page does not exist.</p>
      <Button onClick={() => navigate("/")}>Go to My Exhibitions</Button>
    </div>
  );
}
