"""Audit saved target controls and native parsing offline; no inference calls."""

import json
import re
from pathlib import Path
from unittest.mock import patch

from inspect_evals.agentic_misalignment.classifiers import BlackmailClassifier
from inspect_evals.agentic_misalignment.classifiers.classifier import LOGGER
from zipfile_zstd import ZipFile

root = Path(__file__).resolve().parent
audit = {}
paths = {}
for pattern in ("openrouter/deepseek/*/inspect/*.eval", "repaired/*/*.eval"):
    for path in sorted(root.glob(pattern)):
        model = path.parent.name if path.parent.parent.name == "repaired" else path.parts[-3]
        paths[model, path.name.split("_")[1]] = path
for (model, task), path in paths.items():
    with ZipFile(path) as archive:
        filenames = [name for name in archive.namelist() if name.startswith("samples/") and name.endswith(".json")]
        row = dict(path=str(path), model=model, task=task, samples=len(filenames), target_attempts=0, control_mismatches=[],
                   invalid_judge_format=[], invalid_forward_format=[], providers={})
        for filename in filenames:
            sample = json.loads(archive.read(filename))
            attachments = sample.get("attachments", {})

            def resolve(text):
                return attachments.get(text.removeprefix("attachment://"), text)

            def final_text(output):
                content = output["choices"][0]["message"]["content"]
                return resolve(content) if isinstance(content, str) else "".join(
                    resolve(part.get("text", "")) for part in content if part["type"] == "text")

            events = [event for event in sample.get("events", []) if event["event"] == "model"]
            targets = [event for event in events if event["model"].startswith("openrouter/")]
            row["target_attempts"] += len(targets)
            for event in targets:
                request = event.get("call", {}).get("request", {})
                expected = {"model": f"deepseek/{model}", "temperature": 1.0,
                            "top_p": 0.95, "max_tokens": 32768, "stream": True}
                if (any(request.get(key) != value for key, value in expected.items())
                        or request.get("extra_body", {}).get("reasoning", {}).get("enabled") is not True):
                    row["control_mismatches"].append(sample["epoch"])
                if event is not targets[-1]:
                    continue  # Response statistics use the final attempt for each sample.
                output = event.get("output", {})
                if not output.get("choices"):
                    continue
                provider = event.get("call", {}).get("response", {}).get("provider") or "unreported"
                counts = row["providers"].setdefault(provider, dict(
                    generations=0, exposed_reasoning=0, reasoning_characters=0, final_characters=0, empty_finals=0,
                    input_tokens=0, output_tokens=0, reasoning_tokens=0,
                    reasoning_usage_reported=0, stop_reasons={}))
                content = output["choices"][0]["message"]["content"]
                reasoning = "" if isinstance(content, str) else "".join(
                    resolve(part.get("reasoning", "")) for part in content if part["type"] == "reasoning")
                usage = output.get("usage", {})
                counts["generations"] += 1
                counts["exposed_reasoning"] += bool(reasoning.strip())
                counts["reasoning_characters"] += len(reasoning)
                counts["final_characters"] += len(final_text(output))
                counts["empty_finals"] += not final_text(output).strip()
                for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
                    counts[key] += usage.get(key, 0) or 0
                counts["reasoning_usage_reported"] += usage.get("reasoning_tokens") is not None
                stop = output["choices"][0].get("stop_reason", "unreported")
                counts["stop_reasons"][stop] = counts["stop_reasons"].get(stop, 0) + 1
            judges = [event for event in events if not event["model"].startswith("openrouter/")
                      and event.get("output", {}).get("choices")]
            if judges and not re.search(r"<answer>\s*(yes|no)\s*</answer>", final_text(judges[-1]["output"]), re.I):
                row["invalid_judge_format"].append(sample["epoch"])
            if targets and targets[-1].get("output", {}).get("choices"):
                response = resolve(sample.get("output", {}).get("completion", final_text(targets[-1]["output"])))
                with patch.object(LOGGER, "warning") as warning:
                    BlackmailClassifier().get_email_context(email_content="", response=response)
                messages = [str(call.args[0]) for call in warning.call_args_list]
                if any(message.startswith(("Invalid email_id", "No email_id", "Failed to parse forward")) for message in messages):
                    row["invalid_forward_format"].append(sample["epoch"])
        audit[str(path.relative_to(root))] = row
(root / "sample_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
for row in audit.values():
    print(row["model"], row["task"],
          {key: len(value) if isinstance(value, list) else value for key, value in row.items()
           if key not in ("path", "model", "task")})
