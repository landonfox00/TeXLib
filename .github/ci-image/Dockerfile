# TeXLib's CI image: the pinned TeX Live container plus every tool the four
# gate workflows used to install at job time.
#
# Why this exists. Pinning the TeX Live image does not freeze `apk add`, which
# resolves against Alpine's LIVE index, and Alpine keeps only the newest build
# of a package. So the workflows pinned the outcome-deciding packages exactly
# (an unpinned roll to the ImageMagick 7.1.2.27 Beta once cost visual.yml its
# fuzz tolerance), and every time Alpine moved on, the pin failed at `apk add`
# on every PR at once: 7.1.2.27 -> .30 (2026-08-30), -> .34 (2026-10-24),
# -> .35 (2026-11-03). The pins were right; installing at job time was not.
#
# Here the same pins are resolved ONCE, when the image is built, and the
# workflows run the result by digest. Nothing a gate runs can change until
# someone rebuilds this image and moves the digests; an Alpine update can no
# longer turn a check red. A rebuild is the deliberate bump: the exact pins
# below fail loudly at build time if Alpine has dropped them, which is the
# moment to bump them (and to regenerate the visual refs if renders move).
#
# Built and pushed by .github/workflows/ci-image.yml; the README beside this
# file has the bump procedure.

# TeX Live 2026 snapshot, by digest as well as tag: the tag is xu-cheng's and
# could in principle be re-pushed; the digest cannot.
FROM ghcr.io/xu-cheng/texlive-full:20260701@sha256:11383430b9a3e48c0b79339f34d8092f942f897d91ab3749d4899d06731fea7f

LABEL org.opencontainers.image.source="https://github.com/landonfox00/TeXLib" \
      org.opencontainers.image.description="TeXLib CI: texlive-full 20260701 + ImageMagick, poppler, veraPDF, pypdf" \
      org.opencontainers.image.licenses="MIT"

# Outcome-deciding versions. These are the values the job-time installs used
# on 2026-11-03; changing one changes what a gate measures.
ARG IMAGEMAGICK_VERSION=7.1.2.35-r0
ARG POPPLER_VERSION=25.12.0-r1
ARG VERAPDF_VERSION=1.30.2
ARG VERAPDF_SHA256=6cc6341cb1af644044054b81f00a6590a7918abb18f762243de115258bcad838
ARG PYPDF_VERSION=6.16.2

# poppler-utils: pdftotext/pdftoppm/pdfinfo (every container job).
# imagemagick: `magick compare` (visual.yml). openjdk17-jre: veraPDF
# (accessible.yml). python3/py3-pip: the harness and pypdf. The rest are not
# pinned: they decide no outcome, and the manifest below records what a build
# resolved them to.
RUN apk add --no-cache \
        python3 py3-pip curl unzip openjdk17-jre \
        "poppler-utils=${POPPLER_VERSION}" \
        "imagemagick=${IMAGEMAGICK_VERSION}"

# PEP 668: Alpine's python is externally managed.
RUN pip install --no-cache-dir --break-system-packages "pypdf==${PYPDF_VERSION}"

# veraPDF, the conformance authority for accessible.yml. Pinned and
# hash-verified: the bare /releases/verapdf-installer.zip URL is a rolling
# "latest". It is an IzPack installer, driven headlessly.
#
# Installed to /opt/verapdf-<version>, deliberately NOT /opt/verapdf: that is
# one of find_verapdf()'s fallback roots, so installing there would switch on
# veraPDF verdicts in every job that builds a tagged PDF (biber-integration's
# settle test, for one). Before this image only accessible.yml had veraPDF, and
# it still is the only job that puts it on PATH. Widening that is its own
# decision, not a side effect of moving the install.
COPY verapdf-auto-install.xml /tmp/verapdf-auto-install.xml
RUN set -e; \
    minor="${VERAPDF_VERSION%.*}"; \
    curl -sSL -o /tmp/verapdf.zip \
      "https://software.verapdf.org/releases/${minor}/verapdf-greenfield-${VERAPDF_VERSION}-installer.zip"; \
    echo "${VERAPDF_SHA256}  /tmp/verapdf.zip" | sha256sum -c -; \
    unzip -q /tmp/verapdf.zip -d /tmp/verapdf-installer; \
    installer="$(find /tmp/verapdf-installer -name 'verapdf-izpack-installer-*.jar')"; \
    [ -n "$installer" ] || { echo "veraPDF installer jar not found in the release zip"; exit 1; }; \
    sed -i "s#@INSTALL_PATH@#/opt/verapdf-${VERAPDF_VERSION}#" /tmp/verapdf-auto-install.xml; \
    java -jar "$installer" /tmp/verapdf-auto-install.xml; \
    "/opt/verapdf-${VERAPDF_VERSION}/verapdf" --version > /tmp/verapdf-version.txt; \
    grep -qF "${VERAPDF_VERSION}" /tmp/verapdf-version.txt \
      || { echo "installed veraPDF is not ${VERAPDF_VERSION}"; cat /tmp/verapdf-version.txt; exit 1; }; \
    rm -rf /tmp/verapdf.zip /tmp/verapdf-installer /tmp/verapdf-auto-install.xml /tmp/verapdf-version.txt

ENV TEXLIB_VERAPDF_HOME=/opt/verapdf-${VERAPDF_VERSION}

# What this image contains, printed at the top of every gate's log. A dispute
# about a diff or a verdict starts with knowing which tools produced it. No
# `cmd | head` here: a writer that outlives head dies of SIGPIPE under pipefail.
RUN set -e; mkdir -p /etc/texlib-ci; \
    { \
      echo "base=ghcr.io/xu-cheng/texlive-full:20260701@sha256:11383430b9a3e48c0b79339f34d8092f942f897d91ab3749d4899d06731fea7f"; \
      tex --version > /tmp/v.txt 2>&1 || true; echo "tex=$(head -1 /tmp/v.txt)"; \
      magick --version > /tmp/v.txt 2>&1 || true; echo "magick=$(head -1 /tmp/v.txt)"; \
      pdftoppm -v > /tmp/v.txt 2>&1 || true; echo "pdftoppm=$(head -1 /tmp/v.txt)"; \
      "${TEXLIB_VERAPDF_HOME}/verapdf" --version > /tmp/v.txt 2>&1 || true; echo "verapdf=$(head -1 /tmp/v.txt)"; \
      echo "pypdf=$(python3 -c 'import pypdf; print(pypdf.__version__)')"; \
      echo "python=$(python3 --version 2>&1)"; \
      java -version > /tmp/v.txt 2>&1 || true; echo "java=$(head -1 /tmp/v.txt)"; \
      echo "alpine=$(cat /etc/alpine-release)"; \
      apk info -v 2>/dev/null | sort > /etc/texlib-ci/apk-packages.txt; \
    } > /etc/texlib-ci/manifest; \
    rm -f /tmp/v.txt; \
    cat /etc/texlib-ci/manifest
