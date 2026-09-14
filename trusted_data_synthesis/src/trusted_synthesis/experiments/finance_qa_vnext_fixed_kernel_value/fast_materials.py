"""Immutable material ownership and byte-bound execution validation receipts.

No scientific rule is duplicated: the full loader calls the original kernel
builder on read-only JSON trees. Their deepcopy operation is identity, so its
unchanged constructor logic no longer duplicates gigabytes of token arrays.
Worker projections are explicitly NOT complete fixed_kernel records; only a
privately minted authority can authorize their use with the frozen global ID.
"""

import json
import weakref
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from . import distribution
from . import protocol as p


def _immutable(*_args, **_kwargs):
    raise TypeError("verified material JSON is immutable")


class FrozenList(list):
    """JSON-compatible read-only sequence; safe to share through deepcopy."""

    def __init__(self, values=()):
        if getattr(self, "_sealed", False):
            _immutable()
        list.__init__(
            self,
            (freeze_json(item) if isinstance(item, (dict, list)) else item for item in values),
        )
        self._sealed = True

    __setitem__ = __delitem__ = __iadd__ = __imul__ = _immutable
    append = clear = extend = insert = pop = remove = reverse = sort = _immutable

    def __setattr__(self, name, value):
        if getattr(self, "_sealed", False):
            _immutable()
        object.__setattr__(self, name, value)

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

    def __copy__(self):
        return self

    def __reduce__(self):
        return FrozenList, (list(self),)


class FrozenDict(dict):
    """JSON-compatible read-only mapping; nested members are frozen too."""

    def __init__(self, values=(), **kwargs):
        if getattr(self, "_sealed", False):
            _immutable()
        dict.__init__(
            self, {key: freeze_json(item) for key, item in dict(values, **kwargs).items()}
        )
        self._sealed = True

    __setitem__ = __delitem__ = __ior__ = _immutable
    clear = pop = popitem = setdefault = update = _immutable

    def __setattr__(self, name, value):
        if getattr(self, "_sealed", False):
            _immutable()
        object.__setattr__(self, name, value)

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

    def __copy__(self):
        return self

    def __reduce__(self):
        return FrozenDict, (dict(self),)


def freeze_json(value):
    """Freeze an owned JSON tree once; existing frozen subtrees remain shared."""
    if isinstance(value, (FrozenDict, FrozenList)):
        return value
    if isinstance(value, dict):
        return FrozenDict(value)
    if isinstance(value, list):
        # Avoid a Python recursive call per scalar token. No mutable child,
        # including a malformed nested token array, escapes this conversion.
        return FrozenList(value)
    return value


_MINT = object()
_CACHE = {}
_OWNERS = {}


class VerifiedInputs(FrozenDict):
    """Full immutable inputs minted only after actual files and kernel checks."""

    def __init__(self, values, *, mint, root, files, stamps, refs, receipt, kind="full"):
        p.require(mint is _MINT, "fast_materials.private_verified_constructor")
        super().__init__(values)
        self._mint = mint
        self.root = Path(root)
        self.files = freeze_json(files)
        self._stamps = FrozenDict(stamps)
        self.package_references = freeze_json(refs)
        self.receipt = freeze_json(receipt)
        self.verification = None
        self.kind = kind
        self._identities = FrozenDict({key: id(value) for key, value in self.items()})
        self._code_hash = validator_code_hash()
        self._verified_sealed = True
        _OWNERS[id(self["kernel"])] = weakref.ref(self)

    def __setattr__(self, name, value):
        if getattr(self, "_verified_sealed", False):
            _immutable()
        object.__setattr__(self, name, value)


class VerifiedAuthority(VerifiedInputs):
    """Compact global validation authority without any original token arrays."""


class VerifiedPoolView(VerifiedInputs):
    """Explicit pool projection with byte-verified originals for that pool."""


def validator_code_hash():
    root = Path(__file__).parent
    names = (
        "protocol.py",
        "population.py",
        "distribution.py",
        "materials.py",
        "fast_materials.py",
        "training.py",
        "consumer.py",
    )
    return p.sha(p.encode({name: p.sha(root / name) for name in names}))


def _signature(path):
    value = path.stat()
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _path(root, relative):
    relative = Path(relative)
    p.require(
        not relative.is_absolute() and ".." not in relative.parts,
        "fast_materials.relative_artifact_path",
    )
    value = root / relative
    p.require(
        value.is_file()
        and value.resolve().is_relative_to(root)
        and not any(part.is_symlink() for part in (value, *value.parents)),
        "fast_materials.regular_contained_artifact",
    )
    return value


def _read(root, reference, stamps, *, expected_id=None):
    path = _path(root, reference["path"])
    before = _signature(path)
    raw = path.read_bytes()
    p.require(
        ("bytes" not in reference or len(raw) == reference["bytes"])
        and p.sha(raw) == reference["sha256"]
        and _signature(path) == before,
        "fast_materials.actual_frozen_file_bytes",
    )
    value = json.loads(raw)
    expected_id = reference.get("id", expected_id)
    if expected_id is not None:
        p.require(value["id"] == expected_id, "fast_materials.referenced_content_identity")
    stamps[path] = before
    return value


def require_verified(value):
    p.require(
        type(value) in (VerifiedInputs, VerifiedAuthority, VerifiedPoolView)
        and value._mint is _MINT
        and value._identities == {key: id(item) for key, item in value.items()}
        and value._code_hash == validator_code_hash(),
        "fast_materials.private_immutable_verified_inputs",
    )
    p.require(
        all(_signature(path) == signature for path, signature in value._stamps.items()),
        "fast_materials.verified_source_file_changed",
    )
    return value


def owner_for(kernel):
    reference = _OWNERS.get(id(kernel))
    owner = reference() if reference else None
    if owner is None or owner["kernel"] is not kernel:
        return None
    return owner


def checked_kernel(kernel, kind="fixed_kernel"):
    p.require(kind == "fixed_kernel", "fast_materials.kernel_kind_only")
    owner = owner_for(kernel)
    p.require(owner is not None, "fast_materials.kernel_requires_private_authority")
    require_verified(owner)
    p.require(kernel["id"] == owner.receipt["kernel_id"], "fast_materials.authorized_kernel_id")
    return kernel


def assert_verified_inputs(inputs, kernel, selected_population, registry, outcomes):
    require_verified(inputs)
    p.require(
        inputs["kernel"] is kernel
        and inputs["population"] is selected_population
        and inputs["registry"] is registry
        and inputs["outcomes"] is outcomes,
        "fast_materials.exact_owned_input_objects",
    )
    return inputs


def _input_files(root, files, stamps):
    p.require(
        set(files) == {"population", "registry", "materialization_index"},
        "execution.authoritative_split_material_files",
    )
    loaded = {key: _read(root, reference, stamps) for key, reference in files.items()}
    index, registry = loaded["materialization_index"], loaded["registry"]
    p.checked(index, "materialization_index")
    p.require(
        index["status"] == "COMPLETE_FIXED_MATERIALIZATION"
        and index["collection_complete"] is True
        and index["complete_registered_denominator"] == p.SESSION_CAP
        and index["registry_id"] == registry["id"]
        and index["freeze_id"] == registry["freeze_id"],
        "execution.complete_exact_materialization_index",
    )
    return loaded


def _hydrate_entry(arguments):
    """Authenticate and freeze one original entry in its owning CPU process."""
    root, directory, entry = arguments
    stamps, references = {}, {}
    stored_reference = {**entry["outcome"], "path": str(directory / entry["outcome"]["path"])}
    stored = _read(root, stored_reference, stamps)
    p.checked(stored, "stored_material_outcome")
    reference = stored["original_package_reference"]
    p.require(reference == entry["package"], "materials.index_package_reference")
    original = None
    if reference:
        absolute_reference = {**reference, "path": str(directory / reference["path"])}
        original = _read(root, absolute_reference, stamps)
        p.checked(original, "encoded_original_package")
        references[original["id"]] = absolute_reference
        original = freeze_json(original)
    outcome = p.record("material_outcome", **stored["outcome_fields"], original_package=original)
    p.require(
        outcome["id"] == stored["material_outcome_id"] == entry["outcome_id"]
        and outcome["session_id"] == entry["registered_session_id"],
        "materials.exact_hydrated_outcome",
    )
    return freeze_json(outcome), references, stamps


def load_material_inputs(root, files, *, expected_kernel_id=None, workers=24):
    p.require(
        type(workers) is int and 1 <= workers <= p.CPU_WORKERS,
        "fast_materials.bounded_hydration_workers",
    )
    root = Path(root).resolve()
    key = str(root), p.sha(p.encode(files)), expected_kernel_id, validator_code_hash()
    if key in _CACHE:
        return require_verified(_CACHE[key])
    stamps = {}
    loaded = _input_files(root, files, stamps)
    selected, registry, index = (
        loaded["population"],
        loaded["registry"],
        loaded["materialization_index"],
    )
    directory = Path(files["materialization_index"]["path"]).parent
    outcomes, references = [], {}
    arguments = ((root, directory, entry) for entry in index["entries"])

    def accept(values):
        for outcome, entry_references, entry_stamps in values:
            outcomes.append(outcome)
            references.update(entry_references)
            stamps.update(entry_stamps)

    if workers == 1:
        accept(map(_hydrate_entry, arguments))
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
            # map preserves the original index order. Workers only read frozen
            # files; no token encoding or scientific kernel construction occurs
            # there. The parent calls the original builder exactly once below.
            accept(pool.map(_hydrate_entry, arguments, chunksize=1))
    selected, registry, outcomes = map(freeze_json, (selected, registry, outcomes))
    # Unmodified scientific builder. Frozen subtrees make its deepcopy O(1).
    kernel = freeze_json(distribution.build_kernel(selected, registry, outcomes))
    p.require(
        expected_kernel_id is None or kernel["id"] == expected_kernel_id,
        "fast_materials.exact_original_material_gate_kernel",
    )
    receipt = p.record(
        "material_hydration_receipt",
        kernel_id=kernel["id"],
        input_files_sha256=p.sha(p.encode(files)),
        materialization_index_id=index["id"],
        verified_file_count=len(stamps),
        verified_file_bytes=sum(signature[2] for signature in stamps.values()),
        validator_code_sha256=validator_code_hash(),
        original_builder_used=True,
        CPU_hydration_workers=workers,
        token_tree_immutable=True,
        outcome_based_selection=False,
        token_arrays_reencoded=False,
    )
    inputs = VerifiedInputs(
        dict(population=selected, registry=registry, outcomes=outcomes, kernel=kernel),
        mint=_MINT,
        root=root,
        files=files,
        stamps=stamps,
        refs=references,
        receipt=receipt,
    )
    _CACHE[key] = inputs
    return inputs


def make_receipt(inputs, verification):
    require_verified(inputs)
    p.require(type(inputs) is VerifiedInputs, "fast_materials.full_validation_before_receipt")
    p.checked(verification, "material_input_verification")
    kernel = inputs["kernel"]
    p.require(
        verification["kernel_id"] == kernel["id"]
        and verification["population_id"] == inputs["population"]["id"]
        and verification["registry_id"] == inputs["registry"]["id"]
        and kernel["training_gate"] == kernel["material_gate"] == kernel["dose_gate"] == "PASS",
        "fast_materials.complete_original_global_verification",
    )
    header = p.record(
        "verified_kernel_header",
        source_kernel_id=kernel["id"],
        fields={
            key: value
            for key, value in kernel.items()
            if key not in {"id", "schema_version", "train_packages"}
        },
        train_packages=[
            {key: value for key, value in item.items() if key != "original_package"}
            for item in kernel["train_packages"]
        ],
        contains_original_token_arrays=False,
    )
    receipt = p.record(
        "verified_material_receipt",
        kernel_id=kernel["id"],
        input_files=inputs.files,
        input_files_sha256=p.sha(p.encode(inputs.files)),
        materialization_index_id=inputs.receipt["materialization_index_id"],
        hydration_receipt=inputs.receipt,
        validator_code_sha256=validator_code_hash(),
        kernel_header=header,
        population=inputs["population"],
        registry=inputs["registry"],
        verification=verification,
        package_references=inputs.package_references,
        all_original_file_bytes_verified=True,
        every_registered_outcome_validated=True,
        scientific_kernel_rebuilt_once=True,
        worker_projection_is_not_full_kernel=True,
        token_arrays_repeated_in_receipt=False,
    )
    object.__setattr__(inputs, "verification", freeze_json(verification))
    return receipt


def _projection(header, packages):
    return freeze_json(
        {
            **header["fields"],
            "train_packages": packages,
            "id": header["source_kernel_id"],
            "schema_version": "fixed_kernel_value.v1.verified_kernel_projection",
            "source_kernel_id": header["source_kernel_id"],
            "is_complete_fixed_kernel_record": False,
        }
    )


def load_authority(root, receipt_descriptor, files, *, expected_kernel_id):
    root = Path(root).resolve()
    stamps = {}
    receipt = _read(root, receipt_descriptor, stamps)
    p.checked(receipt, "verified_material_receipt")
    loaded = _input_files(root, files, stamps)
    p.require(
        isinstance(expected_kernel_id, str)
        and receipt["kernel_id"] == expected_kernel_id
        and receipt["input_files"] == files
        and receipt["input_files_sha256"] == p.sha(p.encode(files))
        and receipt["validator_code_sha256"] == validator_code_hash()
        and receipt["materialization_index_id"] == loaded["materialization_index"]["id"]
        and receipt["population"] == loaded["population"]
        and receipt["registry"] == loaded["registry"],
        "fast_materials.frozen_validation_receipt_authority",
    )
    header = p.checked(receipt["kernel_header"], "verified_kernel_header")
    verification = p.checked(receipt["verification"], "material_input_verification")
    p.require(
        header["source_kernel_id"] == verification["kernel_id"] == expected_kernel_id
        and header["fields"]["training_gate"]
        == header["fields"]["material_gate"]
        == header["fields"]["dose_gate"]
        == "PASS"
        and header["fields"]["registered_session_count"] == p.SESSION_CAP
        and header["fields"]["collection_complete"] is True,
        "fast_materials.original_global_gates_required",
    )
    authority = VerifiedAuthority(
        dict(
            population=freeze_json(receipt["population"]),
            registry=freeze_json(receipt["registry"]),
            outcomes=FrozenList(),
            kernel=_projection(header, header["train_packages"]),
        ),
        mint=_MINT,
        root=root,
        files=files,
        stamps=stamps,
        refs=receipt["package_references"],
        receipt=receipt,
        kind="authority",
    )
    object.__setattr__(authority, "verification", freeze_json(verification))
    return authority


def load_training_pool(root, receipt_descriptor, files, *, pool, expected_kernel_id):
    p.require(pool in p.POOLS, "fast_materials.registered_training_pool")
    authority = load_authority(
        root, receipt_descriptor, files, expected_kernel_id=expected_kernel_id
    )
    stamps = dict(authority._stamps)
    packages = []
    for item in authority["kernel"]["train_packages"]:
        if item["pool"] != pool:
            packages.append(item)
            continue
        reference = authority.package_references[item["package_id"]]
        original = _read(authority.root, reference, stamps)
        p.checked(original, "encoded_original_package")
        p.require(
            original["id"] == item["package_id"]
            and original["registered_session_id"] == item["session_id"]
            and original["pool"] == pool
            and original["role"] == "train"
            and original["task_id"] == item["task_id"]
            and original["actual_method"] == item["method"]
            and distribution.canonical_state_id(original["actual_method"], original["full_class"])
            == item["state_id"]
            # Full validation already certified canonical package bytes. _read
            # checks these exact bytes, so no second complete JSON encode is
            # needed here in addition to the content-ID check above.
            and reference["sha256"] == item["original_package_sha256"],
            "fast_materials.exact_current_pool_original_package",
        )
        packages.append(FrozenDict({**item, "original_package": freeze_json(original)}))
    view = VerifiedPoolView(
        dict(
            population=authority["population"],
            registry=authority["registry"],
            outcomes=FrozenList(),
            kernel=_projection(authority.receipt["kernel_header"], packages),
        ),
        mint=_MINT,
        root=authority.root,
        files=files,
        stamps=stamps,
        refs=authority.package_references,
        receipt=authority.receipt,
        kind="pool",
    )
    object.__setattr__(view, "pool", pool)
    object.__setattr__(view, "verification", authority.verification)
    return view
