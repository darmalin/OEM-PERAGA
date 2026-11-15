import { api, ApiError, call, setCsrfToken } from "@ems/api";
import { cn } from "@ems/ui/cn";
import { LayoutGrid, LogOut, Menu, UserRound, X } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { brandOf, type ExhibitorRecord, exhibitorRouteOf, href, type Me, messageOf, navigate, useRoute } from "./lib";
import { AcceptInvite } from "./pages/accept-invite";
import { ContractPage, ExhibitorPage } from "./pages/exhibitor";
import { Home } from "./pages/home";
import { Login } from "./pages/login";
import { OrderFormPage, OrderFormsPage, OrderReviewPage } from "./pages/order-forms";
import { Button, Notice, PageBody } from "./ui";

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

  const target = exhibitorRouteOf(route);
  const record = session.kind === "in" ? (session.me.exhibitors.find((e) => e.exhibitor_lead_id === target?.id) ?? null) : null;
  const brand = brandOf(record);

  // The show's colour on the whole page (styles.css), PERAGA red outside a show.
  useEffect(() => {
    document.documentElement.dataset.theme = brand.theme;
  }, [brand.theme]);

  // Sign-in and password pages fill the screen on their own, as the old manual's.
  if (route === "/accept-invite") {
    // Replacing the history entry drops the used token from the address bar.
    return <AcceptInvite token={search.get("token") ?? ""} onDone={(me) => { signedIn(me); navigate("/", true); }} />;
  }
  if (session.kind === "out") {
    return <Login onDone={(me) => { signedIn(me); if (route === "/login") navigate("/", true); }} />;
  }

  let body;
  if (session.kind === "loading") {
    body = <p role="status" className="py-16 text-center text-label">Loading your portal</p>;
  } else if (session.kind === "error") {
    body = <PageBody className="items-center py-16"><Notice>{session.message}</Notice><Button onClick={load}>Retry</Button></PageBody>;
  } else if (route === "/" || route === "/login") {
    body = <Home me={session.me} />;
  } else {
    const out = () => setSession({ kind: "out" });
    if (!target || !record) body = <NotFound />;
    else if (target.page === "forms") body = <OrderFormsPage record={record} onSignedOut={out} />;
    else if (target.page === "form") body = <OrderFormPage key={target.code} record={record} code={target.code} onSignedOut={out} />;
    else if (target.page === "review") body = <OrderReviewPage key={target.code} record={record} code={target.code} onSignedOut={out} />;
    else if (target.page === "contract") body = <ContractPage record={record} onSignedOut={out} />;
    else body = <ExhibitorPage record={record} onSignedOut={out} />;
  }

  const section = !record || !target ? null : target.page === "exhibitor" ? "home" : target.page === "contract" ? "contract" : "forms";
  return (
    <div className="flex min-h-dvh flex-col">
      <Header
        brand={brand}
        record={record}
        section={section}
        me={session.kind === "in" ? session.me : null}
        onSignOut={() => void signOut()}
      />
      <main className="flex-1">{body}</main>
      <footer className="bg-secondary text-white">
        <div className="mx-auto max-w-[1280px] px-6 max-sm:px-4">
          <p className="py-8 text-center text-[17px]">PERAGA Expo · Online Exhibitor Manual</p>
          <p className="border-t border-white/20 py-6 text-center text-[13px] text-white/75">
            © {new Date().getFullYear()} PERAGA Expo. Questions about your booth, contract, or orders? Contact your sales person.
          </p>
        </div>
      </footer>
    </div>
  );
}

type Section = "home" | "contract" | "forms";

function Header({ brand, record, section, me, onSignOut }: {
  brand: ReturnType<typeof brandOf>;
  record: ExhibitorRecord | null;
  section: Section | null;
  me: Me | null;
  onSignOut: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const base = record ? `/e/${record.exhibitor_lead_id}` : null;
  const links: [Section, string, string][] = base
    ? [["home", "Home", base], ["contract", "Contract & Payments", `${base}/contract`], ["forms", "Order Forms", `${base}/forms`]]
    : [];
  const go = (to: string) => (e: { preventDefault: () => void }) => { e.preventDefault(); setMenuOpen(false); navigate(to); };

  return (
    <header className="sticky top-0 z-30 bg-bg shadow-[0_2px_12px_rgb(0_0_0/0.08)]">
      <div className="mx-auto flex h-[66px] max-w-[1280px] items-center justify-between gap-4 px-6 max-sm:px-4">
        <a href={href(base ?? "/")} onClick={go(base ?? "/")} className="flex shrink-0 items-center rounded-[6px]">
          <img src={brand.logo.src} alt={brand.logo.alt} width={brand.logo.width} height={brand.logo.height} className="h-8 w-auto" />
        </a>
        {me ? (
          <div className="flex items-center gap-4">
            {links.length ? (
              <nav aria-label="Main" className="max-md:hidden">
                <ul className="flex items-center gap-1">
                  {links.map(([key, text, to]) => (
                    <li key={key}>
                      <a href={href(to)} onClick={go(to)} aria-current={section === key ? "page" : undefined}
                        className={cn("rounded-[6px] px-2.5 py-1 text-[15px] font-medium whitespace-nowrap", section === key ? "bg-primary text-on-primary" : "text-ink hover:text-primary")}>
                        {text}
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>
            ) : null}
            <ProfileMenu me={me} onSignOut={onSignOut} />
            {links.length ? (
              <button type="button" className="hidden size-10 items-center justify-center rounded-[8px] border border-line-strong max-md:flex" aria-expanded={menuOpen} aria-controls="mobile-menu" aria-label={menuOpen ? "Close menu" : "Open menu"} onClick={() => setMenuOpen((v) => !v)}>
                {menuOpen ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
      {menuOpen && links.length ? (
        <nav id="mobile-menu" aria-label="Main" className="border-t border-line md:hidden">
          <ul className="flex flex-col px-4 py-2">
            {links.map(([key, text, to]) => (
              <li key={key}>
                <a href={href(to)} onClick={go(to)} aria-current={section === key ? "page" : undefined}
                  className={cn("my-0.5 block rounded-[8px] px-3 py-2.5 text-[15px] font-medium", section === key ? "bg-primary text-on-primary" : "text-ink")}>
                  {text}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
    </header>
  );
}

/** The round profile button of the old manual: who is signed in, other exhibitions, sign out. */
function ProfileMenu({ me, onSignOut }: { me: Me; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    addEventListener("mousedown", close);
    addEventListener("keydown", close);
    return () => {
      removeEventListener("mousedown", close);
      removeEventListener("keydown", close);
    };
  }, [open]);
  const item = "flex w-full items-center gap-2 px-4 py-2.5 text-left text-[14px] font-medium hover:bg-hover";
  return (
    <div ref={box} className="relative">
      <button type="button" aria-haspopup="menu" aria-expanded={open} aria-label="Account" onClick={() => setOpen((v) => !v)}
        className="flex size-10 items-center justify-center rounded-full border-2 border-ink text-ink hover:border-primary hover:text-primary">
        <UserRound className="size-5" aria-hidden />
      </button>
      {open ? (
        <div role="menu" className="absolute right-0 mt-2 w-64 overflow-hidden rounded-[10px] border border-line bg-bg py-1 shadow-[0_8px_24px_rgb(0_0_0/0.12)]">
          <p className="truncate border-b border-line px-4 py-2.5 text-[13px] text-label">{me.email}</p>
          {me.exhibitors.length > 1 ? (
            <MenuLink onClick={() => { setOpen(false); navigate("/"); }} className={item}><LayoutGrid className="size-4" aria-hidden />My Exhibitions</MenuLink>
          ) : null}
          <MenuLink onClick={onSignOut} className={cn(item, "text-[var(--red-fg)]")}><LogOut className="size-4" aria-hidden />Sign Out</MenuLink>
        </div>
      ) : null}
    </div>
  );
}

function MenuLink({ onClick, className, children }: { onClick: () => void; className: string; children: ReactNode }) {
  return <button type="button" role="menuitem" onClick={onClick} className={className}>{children}</button>;
}

function NotFound() {
  return (
    <PageBody className="items-center py-16 text-center">
      <p className="text-[16px] font-semibold">This page does not exist.</p>
      <Button onClick={() => navigate("/")}>Go to My Exhibitions</Button>
    </PageBody>
  );
}
