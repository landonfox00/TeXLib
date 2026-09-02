#!/usr/bin/env python3
# thesis_institutions.py
# ============================================================================
# The worklist of US institutions that could use a thesis profile, and the
# scaffold for writing one.
#
# WHY THIS IS A FETCHER AND NOT A LIST
#
# A checked-in list of ~2,000 university names is wrong the moment it is
# written: institutions merge, rename, close, and start granting doctorates.
# Worse, a hand-assembled one is wrong on day one in ways nobody can see --
# a plausible name for an institution that does not exist reads exactly like a
# correct one. So the list is DERIVED, every time, from IPEDS: the federal
# survey every US institution accepting Title IV aid is required to complete.
#
#   https://nces.ed.gov/ipeds/datacenter/data/HD<year>.zip
#
# HD is the institutional-characteristics file. `HLOFFER` is the highest level
# of offering: 9 = doctorate, 8 = post-master's certificate, 7 = master's.
# Anything below that does not award a thesis, so 7-9 is the universe --
# 2,135 institutions in HD2023, of which 1,283 grant doctorates. (Those numbers
# are much larger than the Carnegie R1/R2 count people usually reach for; do
# not substitute one for the other.)
#
# WHAT THIS DOES NOT DO
#
# It does not research anybody's filing requirements. Margins, committee-page
# wording and font rules live on a graduate school's own site, usually in a PDF,
# and getting one wrong does not produce a bad commit -- it produces a rejected
# dissertation for someone who trusted the profile. `scaffold` therefore emits a
# skeleton whose every institution-specific value is a visible placeholder, with
# a provenance header that has to be filled in by someone who read the source.
#
# Usage:
#   python thesis_institutions.py fetch                 # refresh the worklist
#   python thesis_institutions.py list [--state NV] [-n 20]
#   python thesis_institutions.py next                  # next slug with no profile
#   python thesis_institutions.py scaffold <slug>       # write a profile skeleton
# ============================================================================

from __future__ import annotations

import argparse
import csv
import datetime
import io
import os
import re
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.join(HERE, "Thesis", "profiles")
WORKLIST = os.path.join(PROFILES, "institutions.csv")
SOURCE   = os.path.join(PROFILES, "institutions.source")
BLOCKED  = os.path.join(PROFILES, "institutions.blocked.csv")
PRIORITY = os.path.join(PROFILES, "priority.csv")

IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"
DEFAULT_YEAR = 2023

# Highest level of offering that can involve a thesis or dissertation.
THESIS_LEVELS = {"7", "8", "9"}


def slugify(name):
    """A stable, filename-safe profile slug.

    Deliberately lossy and deliberately not clever: lowercase, ASCII letters and
    digits, hyphen-separated. Two institutions can collide (there are several
    `University of X at Y`), which is why the worklist carries the IPEDS UNITID
    and `scaffold` refuses an ambiguous slug rather than guessing.
    """
    s = name.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def fetch(year=DEFAULT_YEAR, url=None):
    """Download HD<year>.zip and return the thesis-granting rows."""
    url = url or IPEDS_URL.format(year=year)
    sys.stderr.write("fetching %s ...\n" % url)
    with urllib.request.urlopen(url, timeout=120) as r:
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        # latin-1, not utf-8: the file carries Windows-1252 punctuation in a
        # handful of institution names and utf-8 raises on them.
        text = z.read(name).decode("latin-1")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        sys.exit("thesis_institutions: %s parsed to zero rows" % name)
    # The first column carries a UTF-8 BOM. We decode latin-1 above (a few
    # institution names use Windows-1252 punctuation and utf-8 raises on them),
    # so those three BOM bytes arrive as three separate latin-1 characters, NOT
    # as one U+FEFF -- stripping the codepoint silently does nothing and the
    # lookup raises StopIteration. Match on the suffix; that is right under
    # either decoding.
    idcol = next(c for c in rows[0] if c.endswith("UNITID"))
    out = []
    for r_ in rows:
        if r_.get("HLOFFER") not in THESIS_LEVELS:
            continue
        out.append({
            "unitid": r_[idcol],
            "name": r_["INSTNM"].strip(),
            "state": r_.get("STABBR", "").strip(),
            "web": r_.get("WEBADDR", "").strip(),
            "doctoral": "1" if r_.get("HLOFFER") == "9" else "0",
            "slug": slugify(r_["INSTNM"]),
        })
    out.sort(key=lambda d: (d["name"].lower(), d["unitid"]))
    return out


def cmd_fetch(args):
    rows = fetch(args.year, args.url)
    os.makedirs(PROFILES, exist_ok=True)
    with open(WORKLIST, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["slug", "name", "state", "unitid", "doctoral", "web"])
        w.writeheader()
        for r_ in rows:
            w.writerow({k: r_[k] for k in w.fieldnames})
    doc = sum(1 for r_ in rows if r_["doctoral"] == "1")
    dupes = len(rows) - len({r_["slug"] for r_ in rows})
    # A CSV cannot carry a comment, and a worklist with no recorded origin is a
    # list someone will later assume was hand-curated. The sidecar is what makes
    # the committed copy auditable and tells you when it is stale.
    with open(SOURCE, "w", encoding="utf-8", newline="\n") as f:
        f.write("source: %s\n" % (args.url or IPEDS_URL.format(year=args.year)))
        f.write("accessed: %s\n" % today())
        f.write("survey: IPEDS HD%s (institutional characteristics)\n" % args.year)
        f.write("filter: HLOFFER in {7,8,9} -- master's, post-master's, doctorate\n")
        f.write("rows: %d\n" % len(rows))
        f.write("doctorate_granting: %d\n" % doc)
        f.write("regenerate: python thesis_institutions.py fetch\n")
    print("wrote %s" % os.path.relpath(WORKLIST, HERE))
    print("wrote %s" % os.path.relpath(SOURCE, HERE))
    print("  %d institutions offering a master's or above" % len(rows))
    print("  %d of them doctorate-granting" % doc)
    print("  source: %s (accessed %s)"
          % (args.url or IPEDS_URL.format(year=args.year), today()))
    if dupes:
        print("  %d slug collision(s); scaffold will refuse those by name" % dupes)
    return 0


def today():
    return datetime.date.today().isoformat()


def load_worklist():
    if not os.path.exists(WORKLIST):
        sys.exit("thesis_institutions: no worklist yet -- run `fetch` first")
    with open(WORKLIST, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# Profiles whose filename is not the IPEDS slug. A profile is named for what a
# document types -- `profile=unr' -- and nobody is going to write
# `profile=university-of-nevada-reno'. Without this map the worklist reports UNR
# as unwritten and `next' would eventually scaffold a second, duplicate profile
# for an institution that already has one.
#
# Add an entry when a profile takes a short name. Keep the IPEDS slug on the
# left: that side is generated and must match the worklist exactly.
ALIASES = {
    "university-of-nevada-reno": "unr",
}


def existing_profiles():
    """Profile slugs present on disk, expressed in IPEDS-slug terms."""
    if not os.path.isdir(PROFILES):
        return set()
    have = {os.path.splitext(f)[0] for f in os.listdir(PROFILES)
            if f.endswith(".tex")}
    # generic is the class's built-in fallback, not an institution.
    have.discard("generic")
    return have | {ipeds for ipeds, short in ALIASES.items() if short in have}


def blocked_slugs():
    """Institutions a research pass could not complete, and why.

    Without this, `next` re-picks the same institution every run forever: it
    returns the first slug with no profile, and an institution whose filing
    requirements are behind a login, only in a scanned PDF, or simply not
    published never gets one. One unresearchable institution would stall the
    whole queue.

    Blocking is not a verdict on the institution -- it is a note that THIS
    attempt failed, with the date and reason, so a later attempt can be
    deliberate rather than accidental.
    """
    if not os.path.exists(BLOCKED):
        return {}
    out = {}
    with open(BLOCKED, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["slug"]] = row
    return out


def cmd_block(args):
    """Record that a research pass could not complete for this institution."""
    rows = load_worklist()
    match = [r_ for r_ in rows if r_["slug"] == args.slug]
    if not match:
        sys.exit("thesis_institutions: %r is not in the worklist" % args.slug)
    blocked = blocked_slugs()
    if args.slug in blocked and not args.force:
        sys.exit("thesis_institutions: %r is already blocked (%s)"
                 % (args.slug, blocked[args.slug].get("reason", "")))
    exists = os.path.exists(BLOCKED)
    with open(BLOCKED, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "date", "reason"])
        if not exists:
            w.writeheader()
        w.writerow({"slug": args.slug, "date": today(), "reason": args.reason})
    print("blocked %s (%s)" % (args.slug, args.reason))
    print("`next` will skip it. Remove the row from %s to retry."
          % os.path.relpath(BLOCKED, HERE))
    return 0


def cmd_list(args):
    rows = load_worklist()
    if args.state:
        rows = [r_ for r_ in rows if r_["state"].upper() == args.state.upper()]
    if args.doctoral:
        rows = [r_ for r_ in rows if r_["doctoral"] == "1"]
    have = existing_profiles()
    shown = rows[:args.number] if args.number else rows
    for r_ in shown:
        print("  %-3s %-46s %-2s  %s"
              % ("[x]" if r_["slug"] in have else "[ ]",
                 r_["name"][:46], r_["state"], r_["slug"]))
    print("\n%d shown of %d; %d have a profile"
          % (len(shown), len(rows), sum(1 for r_ in rows if r_["slug"] in have)))
    return 0


def load_priority():
    """The ranked head of the queue, as [(rank, slug)] in rank order.

    Optional: a checkout with no priority.csv falls straight back to
    alphabetical, which is what this tool did before the file existed.
    """
    if not os.path.exists(PRIORITY):
        return []
    out = []
    with open(PRIORITY, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                out.append((int(row["rank"]), row["slug"]))
            except (KeyError, ValueError):
                continue          # a malformed row must not stall the queue
    return sorted(out)


def cmd_next(args):
    """The next institution to work on: ranked head first, then alphabetical.

    Two orders, in sequence, for two different reasons.

    priority.csv comes first because alphabetical order starts at "A T Still
    University of Health Sciences" and does not reach the institutions that
    actually graduate the most doctorates for something like 1,900 rows. The
    file is the NSF HERD research-expenditure ranking, and its provenance is in
    priority.source.

    Alphabetical is the fallback, and stays the fallback: it is the only order
    that is stable as the worklist changes underneath, and it makes "where did
    we get to" answerable from the profiles directory alone with no separate
    cursor to lose. Nothing is skipped by ranking -- only reordered.
    """
    have = existing_profiles()
    skip = set(blocked_slugs())
    rows = {r_["slug"]: r_ for r_ in load_worklist()}

    def emit(r_, rank=None):
        if args.quiet:
            print(r_["slug"])
        else:
            where = "" if rank is None else "  (HERD R&D rank %d)" % rank
            print("%s%s\n  %s (%s)\n  %s"
                  % (r_["slug"], where, r_["name"], r_["state"],
                     r_["web"] or "(no web address on file)"))

    for rank, slug in load_priority():
        # A priority slug that is not in the worklist is a stale row, not a
        # reason to stop -- IPEDS renames and merges institutions every year.
        if slug in rows and slug not in have and slug not in skip:
            emit(rows[slug], rank)
            return 0

    for r_ in load_worklist():
        if r_["slug"] not in have and r_["slug"] not in skip:
            emit(r_)
            return 0
    n_blocked = len(blocked_slugs())
    print("no institution left to work on"
          + (" (%d blocked; see %s)" % (n_blocked, os.path.basename(BLOCKED))
             if n_blocked else ""))
    return 0


SKELETON = """\
%% profiles/{slug}.tex -- {name}
%% ============================================================================
%% UNVERIFIED SKELETON. Every value below is a placeholder. Do not file a thesis
%% against this profile until someone has read {name}'s own
%% graduate-school filing requirements and replaced them.
%%
%% Provenance -- fill these in when you do:
%%   source:   <URL of the filing-requirements page or PDF>
%%   accessed: <YYYY-MM-DD>
%%   checked:  <who read it>
%%
%% IPEDS UNITID {unitid} | {state} | {web}
%% Generated {date} by thesis_institutions.py from IPEDS HD{year}, which
%% supplies the institution's NAME and nothing else. IPEDS does not publish
%% filing requirements; it cannot tell you a margin.
%%
%% See Thesis/README.md for what a profile owns, and profiles/unr.tex for a
%% complete worked example.

\\thesisinstitution{{{name}}}

%% --- Filing figures ----------------------------------------------------------
%% PLACEHOLDER: these are texlib-thesis's neutral defaults, not {name}'s
%% rules. Check the margin and spacing requirements and correct them.
\\thesissetgeometry{{left=1in, right=1in, top=1in, bottom=1in}}
\\thesissetspacing{{double}}

%% --- Title page --------------------------------------------------------------
%% PLACEHOLDER: the class's neutral title page is used until this is written.
%% Copy the \\renewcommand from profiles/unr.tex and adjust the wording.
%%
%% \\renewcommand{{\\thesistitlepage}}{{...}}

%% --- Committee approval page --------------------------------------------------
%% PLACEHOLDER: likewise. Most graduate schools prescribe this page exactly --
%% signature lines, ordering, whether a seal or logo appears.
%%
%% \\renewcommand{{\\thesisapprovalpage}}{{...}}

%% Until the two pages above are written this profile renders the neutral ones,
%% which are correct-looking and NOT this institution's. \\statementplaceholder
%% is not used here because a thesis page has no natural place to show a red
%% banner -- which is exactly why this file says so at the top instead.
"""


def cmd_scaffold(args):
    rows = load_worklist()
    matches = [r_ for r_ in rows if r_["slug"] == args.slug]
    if not matches:
        near = [r_ for r_ in rows if args.slug in r_["slug"]][:5]
        sys.stderr.write("thesis_institutions: no institution with slug %r\n"
                         % args.slug)
        for r_ in near:
            sys.stderr.write("  did you mean %s (%s)?\n" % (r_["slug"], r_["name"]))
        return 2
    if len(matches) > 1:
        sys.stderr.write("thesis_institutions: slug %r is ambiguous -- %d "
                         "institutions share it:\n" % (args.slug, len(matches)))
        for r_ in matches:
            sys.stderr.write("  UNITID %s  %s (%s)\n"
                             % (r_["unitid"], r_["name"], r_["state"]))
        sys.stderr.write("Disambiguate by hand; do not guess.\n")
        return 2
    inst = matches[0]
    dest = os.path.join(PROFILES, inst["slug"] + ".tex")
    if os.path.exists(dest) and not args.force:
        sys.stderr.write("thesis_institutions: %s already exists (use --force)\n"
                         % os.path.relpath(dest, HERE))
        return 2
    body = SKELETON.format(slug=inst["slug"], name=inst["name"],
                           unitid=inst["unitid"], state=inst["state"],
                           web=inst["web"] or "no web address on file",
                           date=today(), year=args.year)
    os.makedirs(PROFILES, exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("wrote %s" % os.path.relpath(dest, HERE))
    print()
    print("It is a SKELETON: it renders the institution-neutral pages and says so.")
    print("Read %s's filing requirements, fill in the provenance"
          % inst["name"])
    print("header, and replace the three placeholder blocks before anyone files")
    print("a thesis against it.")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="thesis_institutions",
        description="Derive the US thesis-granting institution worklist from "
                    "IPEDS, and scaffold a profile for one of them.")
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="refresh the worklist from IPEDS")
    f.add_argument("--year", type=int, default=DEFAULT_YEAR)
    f.add_argument("--url", help="override the source URL (offline mirror)")
    f.set_defaults(func=cmd_fetch)

    l = sub.add_parser("list", help="show the worklist and which have profiles")
    l.add_argument("--state", metavar="XX")
    l.add_argument("--doctoral", action="store_true",
                   help="doctorate-granting only")
    l.add_argument("-n", "--number", type=int, default=20)
    l.set_defaults(func=cmd_list)

    bk = sub.add_parser("block",
                        help="record that a research pass could not complete, "
                             "so `next` stops re-picking it")
    bk.add_argument("slug")
    bk.add_argument("reason", help="why -- e.g. 'requirements behind a login'")
    bk.add_argument("--force", action="store_true", help="re-block")
    bk.set_defaults(func=cmd_block)

    n = sub.add_parser("next", help="next institution alphabetically with no profile")
    n.add_argument("-q", "--quiet", action="store_true", help="print the slug only")
    n.set_defaults(func=cmd_next)

    s = sub.add_parser("scaffold", help="write a profile skeleton")
    s.add_argument("slug")
    s.add_argument("--year", type=int, default=DEFAULT_YEAR)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_scaffold)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    args = build_parser().parse_args()
    sys.exit(args.func(args))
