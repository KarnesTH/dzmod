#!/bin/sh
set -eu

REPO="KarnesTH/dzmod"
BIN_NAME="dzmod"

info() { printf '%s\n' "$1"; }
error() { printf 'Error: %s\n' "$1" >&2; exit 1; }

detect_platform() {
    case "$(uname -s)" in
        Linux) ;;
        *) error "dzmod only supports Linux." ;;
    esac
}

check_requirements() {
    command -v curl >/dev/null 2>&1 || error "curl is required."
    command -v uv >/dev/null 2>&1 || error "uv is required: https://docs.astral.sh/uv/getting-started/installation/"
}

latest_ref() {
    tag=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" 2>/dev/null \
        | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
    if [ -n "$tag" ]; then
        printf '%s' "$tag"
    else
        printf 'main'
    fi
}

install_dzmod() {
    ref=$(latest_ref)
    info "Installing ${BIN_NAME} (${ref}) ..."
    uv tool install --force "git+https://github.com/${REPO}@${ref}"
}

check_path() {
    bin_dir=$(uv tool dir --bin)
    case ":${PATH}:" in
        *":${bin_dir}:"*) ;;
        *)
            info ""
            info "Warning: ${bin_dir} is not in your PATH."
            info "Add this line to your shell profile (~/.bashrc, ~/.zshrc, ...):"
            info "  export PATH=\"${bin_dir}:\$PATH\""
            ;;
    esac
}

detect_platform
check_requirements
install_dzmod
check_path

info ""
info "Done. Run '${BIN_NAME} setup' to configure dzmod."