#!/usr/bin/env python3
"""Generate Gherkin .feature stub files for uncovered requirements.

This module creates placeholder BDD feature files so that every requirement
in the Cameo export has at least one corresponding scenario.  The generated
stubs intentionally contain a failing step
(``Then it should fail because it is not yet implemented``) to ensure the
pipeline stays red until real tests are authored.

Used by ``traceability_checker.py`` programmatically and can also be invoked
from the command line.

Typical CLI usage::

    python stub_generator.py \
        --requirements build/requirements.json \
        --output-dir bdd/features/automated \
        --non-test-output-dir bdd/features/non_test
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AUTOMATED_VERIFICATION_METHODS = {"Test", "Demonstration"}
_MANUAL_VERIFICATION_METHODS = {"Analysis", "Inspection"}

_METHOD_TO_SUBDIR: Dict[str, str] = {
    "Analysis": "analysis",
    "Inspection": "inspection",
    "Demonstration": "demonstration",
}

# Tags applied to every stub
_AUTO_TAG = "@AUTO_GENERATED"
_STUB_TAG = "@STUB"
_MANUAL_TAG = "@manual"

# Inline fallback template used when the Jinja2 file is unavailable.
_INLINE_TEMPLATE = textwrap.dedent(
    """\
    {tags}
    Feature: {requirement_id} - {title}
      {description}

      Verification Method: {verification_method}
      Verification Criteria: {verification_criteria}

      Scenario: Verify {requirement_id} - {title}
        Given the system is configured for {method_lower} verification of "{requirement_id}"
        When the {method_lower} verification is performed
        Then it should fail because it is not yet implemented
    """
)

_JINJA2_TEMPLATE_NAME = "stub_scenario.feature.j2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert *text* to a filesystem-safe lower-case slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text)
    return slug.strip("_").lower()


def _load_requirements(path: Path) -> List[Dict[str, Any]]:
    """Load and return the ``requirements`` list from a Cameo JSON export."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    requirements: List[Dict[str, Any]] = data.get("requirements", [])
    if not requirements:
        logger.warning("No requirements found in %s", path)
    return requirements


def _try_load_jinja2_template(template_dir: Optional[Path] = None):
    """Attempt to load the Jinja2 template; return *None* on failure."""
    try:
        from jinja2 import Environment, FileSystemLoader  # type: ignore[import-untyped]
    except ImportError:
        logger.debug("Jinja2 is not installed – using inline template.")
        return None

    if template_dir is None:
        template_dir = Path(__file__).resolve().parent / "templates"

    if not (template_dir / _JINJA2_TEMPLATE_NAME).is_file():
        logger.debug(
            "Jinja2 template %s not found in %s – using inline template.",
            _JINJA2_TEMPLATE_NAME,
            template_dir,
        )
        return None

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        keep_trailing_newline=True,
    )
    return env.get_template(_JINJA2_TEMPLATE_NAME)


def _render_stub(
    requirement: Dict[str, Any],
    *,
    is_manual: bool,
    jinja_template: Any = None,
) -> str:
    """Render a single Gherkin stub for *requirement*.

    Parameters
    ----------
    requirement:
        A single requirement dict from the Cameo export.
    is_manual:
        Whether this requirement uses a manual verification method.
    jinja_template:
        An optional pre-loaded Jinja2 ``Template`` object.  When *None* the
        built-in inline template is used instead.

    Returns
    -------
    str
        The full text of the ``.feature`` file.
    """
    req_id: str = requirement["requirementId"]
    title: str = requirement.get("title", req_id)
    description: str = requirement.get("description", "")
    verification_method: str = requirement.get("verificationMethod", "Test")
    verification_criteria: str = requirement.get("verificationCriteria", "")

    if jinja_template is not None:
        return jinja_template.render(
            requirement_id=req_id,
            title=title,
            description=description,
            verification_method=verification_method,
            verification_criteria=verification_criteria,
            is_manual=is_manual,
        )

    # Inline fallback
    if is_manual:
        tags = f"{_MANUAL_TAG} {_STUB_TAG} {_AUTO_TAG}"
    else:
        tags = f"{_STUB_TAG} {_AUTO_TAG}"

    return _INLINE_TEMPLATE.format(
        tags=tags,
        requirement_id=req_id,
        title=title,
        description=description,
        verification_method=verification_method,
        verification_criteria=verification_criteria,
        method_lower=verification_method.lower(),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_stubs(
    requirements: List[Dict[str, Any]],
    output_dir: Path,
    non_test_output_dir: Path,
    *,
    covered_ids: Optional[set[str]] = None,
    template_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> List[Path]:
    """Generate Gherkin stubs for uncovered requirements.

    Parameters
    ----------
    requirements:
        The full list of requirement dicts from the Cameo export.
    output_dir:
        Target directory for automated (Test / Demonstration) stubs.
    non_test_output_dir:
        Target base directory for manual stubs (Analysis / Inspection).
        Sub-directories ``analysis/``, ``inspection/``, or
        ``demonstration/`` are created automatically.
    covered_ids:
        Optional set of requirement IDs that already have feature files.
        When *None*, stubs are generated for **all** requirements (useful
        for bootstrapping).
    template_dir:
        Override directory for Jinja2 templates.
    dry_run:
        When *True*, no files are written and the function only returns what
        *would* be created.

    Returns
    -------
    list[Path]
        Paths of the feature files that were (or would be) created.
    """
    if covered_ids is None:
        covered_ids = set()

    jinja_template = _try_load_jinja2_template(template_dir)

    created: List[Path] = []

    for req in requirements:
        req_id: str = req["requirementId"]

        if req_id in covered_ids:
            logger.debug("Skipping %s – already covered.", req_id)
            continue

        verification_method: str = req.get("verificationMethod", "Test")
        is_manual = verification_method in _MANUAL_VERIFICATION_METHODS

        # Determine target path
        filename = f"{_slugify(req_id)}.feature"

        if verification_method in _AUTOMATED_VERIFICATION_METHODS:
            target_path = output_dir / filename
        else:
            subdir = _METHOD_TO_SUBDIR.get(verification_method, verification_method.lower())
            target_path = non_test_output_dir / subdir / filename

        # Never overwrite existing stubs
        if target_path.exists():
            logger.info("Stub already exists, skipping: %s", target_path)
            continue

        content = _render_stub(req, is_manual=is_manual, jinja_template=jinja_template)

        if not dry_run:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            logger.info("Created stub: %s", target_path)

        created.append(target_path)

    return created


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Gherkin stub files for uncovered requirements.",
    )
    parser.add_argument(
        "--requirements",
        required=True,
        type=Path,
        help="Path to the Cameo requirements JSON export.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for automated (Test/Demonstration) feature stubs.",
    )
    parser.add_argument(
        "--non-test-output-dir",
        required=True,
        type=Path,
        help="Base directory for manual (Analysis/Inspection) feature stubs.",
    )
    parser.add_argument(
        "--template-dir",
        type=Path,
        default=None,
        help="Override directory containing Jinja2 templates.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without writing files.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for CLI invocation.

    Returns
    -------
    int
        ``0`` on success, ``1`` on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    if not args.requirements.is_file():
        logger.error("Requirements file not found: %s", args.requirements)
        return 1

    requirements = _load_requirements(args.requirements)

    created = generate_stubs(
        requirements,
        output_dir=args.output_dir,
        non_test_output_dir=args.non_test_output_dir,
        template_dir=args.template_dir,
        dry_run=args.dry_run,
    )

    action = "Would create" if args.dry_run else "Created"
    logger.info("%s %d stub(s).", action, len(created))
    for p in created:
        logger.info("  %s", p)

    return 0


if __name__ == "__main__":
    sys.exit(main())
