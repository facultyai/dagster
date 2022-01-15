import os
from typing import TYPE_CHECKING, Any, Callable, Dict, List, NamedTuple, Optional, Union, cast

from dagster import check, seven
from dagster.core.errors import DagsterInvalidEventMetadata
from dagster.serdes import whitelist_for_serdes
from dagster.utils.backcompat import experimental_class_warning

if TYPE_CHECKING:
    from dagster.core.definitions.events import AssetKey

EventMetadataEntryData = Union[
    "TableSchemaMetadataEntryData",
    "DagsterAssetMetadataEntryData",
    "DagsterPipelineRunMetadataEntryData",
    "FloatMetadataEntryData",
    "IntMetadataEntryData",
    "JsonMetadataEntryData",
    "MarkdownMetadataEntryData",
    "PathMetadataEntryData",
    "PythonArtifactMetadataEntryData",
    "TableMetadataEntryData",
    "TextMetadataEntryData",
    "UrlMetadataEntryData",
]

ParseableMetadataEntryData = Union[
    EventMetadataEntryData,
    dict,
    float,
    int,
    list,
    str,
]


def last_file_comp(path: str) -> str:
    return os.path.basename(os.path.normpath(path))


def parse_metadata_entry(label: str, value: ParseableMetadataEntryData) -> "EventMetadataEntry":
    check.str_param(label, "label")

    if isinstance(value, (EventMetadataEntry, PartitionMetadataEntry)):
        raise DagsterInvalidEventMetadata(
            f"Expected a metadata value, found an instance of {value.__class__.__name__}. Consider "
            "instead using a EventMetadata wrapper for the value, or using the `metadata_entries` "
            "parameter to pass in a List[EventMetadataEntry|PartitionMetadataEntry]."
        )

    if isinstance(value, EntryDataUnion):
        return EventMetadataEntry(label, None, value)

    if isinstance(value, str):
        return EventMetadataEntry.text(value, label)

    if isinstance(value, float):
        return EventMetadataEntry.float(value, label)

    if isinstance(value, int):
        return EventMetadataEntry.int(value, label)

    if isinstance(value, dict):
        try:
            # check that the value is JSON serializable
            seven.dumps(value)
            return EventMetadataEntry.json(value, label)
        except TypeError:
            raise DagsterInvalidEventMetadata(
                f'Could not resolve the metadata value for "{label}" to a JSON serializable value. '
                "Consider wrapping the value with the appropriate EventMetadata type."
            )

    raise DagsterInvalidEventMetadata(
        f'Could not resolve the metadata value for "{label}" to a known type. '
        f"Its type was {type(value)}. Consider wrapping the value with the appropriate "
        "EventMetadata type."
    )


def parse_metadata(
    metadata: Dict[str, ParseableMetadataEntryData],
    metadata_entries: List[Union["EventMetadataEntry", "PartitionMetadataEntry"]],
) -> List[Union["EventMetadataEntry", "PartitionMetadataEntry"]]:
    if metadata and metadata_entries:
        raise DagsterInvalidEventMetadata(
            "Attempted to provide both `metadata` and `metadata_entries` arguments to an event. "
            "Must provide only one of the two."
        )

    if metadata_entries:
        return check.list_param(
            metadata_entries, "metadata_entries", (EventMetadataEntry, PartitionMetadataEntry)
        )

    return [
        parse_metadata_entry(k, v)
        for k, v in check.opt_dict_param(metadata, "metadata", key_type=str).items()
    ]


## Event metadata data types


@whitelist_for_serdes
class TextMetadataEntryData(
    NamedTuple(
        "_TextMetadataEntryData",
        [
            ("text", Optional[str]),
        ],
    )
):
    """Container class for text metadata entry data.

    Args:
        text (Optional[str]): The text data.
    """

    def __new__(cls, text: Optional[str]):
        return super(TextMetadataEntryData, cls).__new__(
            cls, check.opt_str_param(text, "text", default="")
        )


@whitelist_for_serdes
class UrlMetadataEntryData(
    NamedTuple(
        "_UrlMetadataEntryData",
        [
            ("url", Optional[str]),
        ],
    )
):
    """Container class for URL metadata entry data.

    Args:
        url (Optional[str]): The URL as a string.
    """

    def __new__(cls, url: Optional[str]):
        return super(UrlMetadataEntryData, cls).__new__(
            cls, check.opt_str_param(url, "url", default="")
        )


@whitelist_for_serdes
class PathMetadataEntryData(
    NamedTuple(
        "_PathMetadataEntryData",
        [
            ("path", Optional[str]),
        ],
    )
):
    """Container class for path metadata entry data.

    Args:
        path (Optional[str]): The path as a string.
    """

    def __new__(cls, path: Optional[str]):
        return super(PathMetadataEntryData, cls).__new__(
            cls, check.opt_str_param(path, "path", default="")
        )


@whitelist_for_serdes
class TableMetadataEntryData(
    NamedTuple(
        "_TableMetadataEntryData",
        [
            ("data", List[Dict[str, object]]),
        ],
    )
):
    """Container class for table metadata entry data.

    Args:
        data (List[Dict[str, object]]): The data as a list of rows. Each row is
            a dictionary mapping field names to values.
    """

    def __new__(cls, data: List[Dict[str, object]]):
        return super(TableMetadataEntryData, cls).__new__(
            cls,
            check.opt_list_param(data, "data", of_type=dict),
        )


@whitelist_for_serdes
class JsonMetadataEntryData(
    NamedTuple(
        "_JsonMetadataEntryData",
        [
            ("data", Dict[str, Any]),
        ],
    )
):
    """Container class for JSON metadata entry data.

    Args:
        data (Dict[str, Any]): The JSON data.
    """

    def __new__(cls, data: Optional[Dict[str, Any]]):
        return super(JsonMetadataEntryData, cls).__new__(
            cls, check.opt_dict_param(data, "data", key_type=str)
        )


@whitelist_for_serdes
class MarkdownMetadataEntryData(
    NamedTuple(
        "_MarkdownMetadataEntryData",
        [
            ("md_str", Optional[str]),
        ],
    )
):
    """Container class for markdown metadata entry data.

    Args:
        md_str (Optional[str]): The markdown as a string.
    """

    def __new__(cls, md_str: Optional[str]):
        return super(MarkdownMetadataEntryData, cls).__new__(
            cls, check.opt_str_param(md_str, "md_str", default="")
        )


@whitelist_for_serdes
class PythonArtifactMetadataEntryData(
    NamedTuple(
        "_PythonArtifactMetadataEntryData",
        [
            ("module", str),
            ("name", str),
        ],
    )
):
    """Container class for python artifact metadata entry data.

    Args:
        module (str): The module where the python artifact can be found
        name (str): The name of the python artifact
    """

    def __new__(cls, module: str, name: str):
        return super(PythonArtifactMetadataEntryData, cls).__new__(
            cls, check.str_param(module, "module"), check.str_param(name, "name")
        )


@whitelist_for_serdes
class FloatMetadataEntryData(
    NamedTuple(
        "_FloatMetadataEntryData",
        [
            ("value", Optional[float]),
        ],
    )
):
    """Container class for float metadata entry data.

    Args:
        value (Optional[float]): The float value.
    """

    def __new__(cls, value: Optional[float]):
        return super(FloatMetadataEntryData, cls).__new__(
            cls, check.opt_float_param(value, "value")
        )


@whitelist_for_serdes
class IntMetadataEntryData(
    NamedTuple(
        "_IntMetadataEntryData",
        [
            ("value", Optional[int]),
        ],
    )
):
    """Container class for int metadata entry data.

    Args:
        value (Optional[int]): The int value.
    """

    def __new__(cls, value: Optional[int]):
        return super(IntMetadataEntryData, cls).__new__(cls, check.opt_int_param(value, "value"))


@whitelist_for_serdes
class DagsterPipelineRunMetadataEntryData(
    NamedTuple(
        "_DagsterPipelineRunMetadataEntryData",
        [
            ("run_id", str),
        ],
    )
):
    """Representation of a dagster pipeline run.

    Args:
        run_id (str): The pipeline run id
    """

    def __new__(cls, run_id: str):
        return super(DagsterPipelineRunMetadataEntryData, cls).__new__(
            cls, check.str_param(run_id, "run_id")
        )


@whitelist_for_serdes
class DagsterAssetMetadataEntryData(
    NamedTuple("_DagsterAssetMetadataEntryData", [("asset_key", "AssetKey")])
):
    """Representation of a dagster asset.

    Args:
        asset_key (AssetKey): The dagster asset key
    """

    def __new__(cls, asset_key: "AssetKey"):
        from dagster.core.definitions.events import AssetKey

        return super(DagsterAssetMetadataEntryData, cls).__new__(
            cls, check.inst_param(asset_key, "asset_key", AssetKey)
        )


@whitelist_for_serdes
class TableSchemaMetadataEntryData(NamedTuple("_TableSchemaMetadataEntryData", [("schema", Dict)])):
    """Representation of a schema for tabular data. Schema must be formatted as a
    `Frictionless Table Schema<https://specs.frictionlessdata.io//table-schema/>`,
    with the following modifications:

    - The `type` of each field MAY be an arbitrary string (i.e. it is not restricted
      to Frictionless types).
    - Field `constraints` descriptor MAY contain a property `other` which
      contains an array of strings. Each element should describe a constraint
      that is not expressible with predefined Frictionless constraint types.
    - A top-level property `constraints` MAY be included. This value is a
      descriptor for "table-level" constraints. Presently only one property,
      `other` is supported. This should contain a list of strings describing
      arbitrary table-level constraints.

    .. code-block:: python

            # example schema
            {
                "constraints": {
                    "other": [
                        "foo > bar",
                    ],
                },
                "fields": [
                    {
                        "name": "foo",
                        "title": "Foo",
                        "type": "string",
                        "description": "Foo description",
                        "constraints": {
                            "required": True,
                            "other": [
                                "starts with the letter 'a'",
                            ],
                        },
                    },
                    {
                        "name": "bar",
                        "type": "string",
                    },
                    {
                        "name": "baz",
                        "type": "some_custom_type",
                        "constraints": {
                            "unique": True,
                        },
                    },
                ],
            }

    Args:
        schema (Dict): The dictionary containing the schema representation.
    """

    # TODO: this is rough-- we should use JSONSchema here and return a rich
    # error message.
    @staticmethod
    def is_valid(schema):
        try:
            check.inst(schema, dict)
            check.list_elem(schema, "fields", of_type=dict)
            for field in schema["fields"]:
                check.str_elem(field, "name")
        except (check.CheckError, KeyError):
            return False

    def __new__(cls, schema: Dict):
        if not TableSchemaMetadataEntryData.is_valid(schema):
            raise DagsterInvalidEventMetadata("Passed invalid table schema.")
        return super(TableSchemaMetadataEntryData, cls).__new__(
            cls, check.dict_param(schema, "schema")
        )


## for runtime checks

EntryDataUnion = (
    TextMetadataEntryData,
    UrlMetadataEntryData,
    PathMetadataEntryData,
    TableMetadataEntryData,
    JsonMetadataEntryData,
    MarkdownMetadataEntryData,
    FloatMetadataEntryData,
    IntMetadataEntryData,
    PythonArtifactMetadataEntryData,
    DagsterAssetMetadataEntryData,
    DagsterPipelineRunMetadataEntryData,
    TableSchemaMetadataEntryData,
)


class EventMetadata:
    """Utility class to wrap metadata values passed into Dagster events so that they can be
    displayed in Dagit and other tooling.

    .. code-block:: python

        @op
        def emit_metadata(context, df):
            yield AssetMaterialization(
                asset_key="my_dataset",
                metadata={
                    "my_text_label": "hello",
                    "dashboard_url": EventMetadata.url("http://mycoolsite.com/my_dashboard"),
                    "num_rows": 0,
                },
            )
    """

    @staticmethod
    def text(text: str) -> "TextMetadataEntryData":
        """Static constructor for a metadata value wrapping text as
        :py:class:`TextMetadataEntryData`. Can be used as the value type for the `metadata`
        parameter for supported events. For example:

        .. code-block:: python

            @op
            def emit_metadata(context, df):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata={
                        "my_text_label": EventMetadata.text("hello")
                    },
                )

        Args:
            text (str): The text string for a metadata entry.
        """
        return TextMetadataEntryData(text)

    @staticmethod
    def url(url: str) -> "UrlMetadataEntryData":
        """Static constructor for a metadata value wrapping a URL as
        :py:class:`UrlMetadataEntryData`. Can be used as the value type for the `metadata`
        parameter for supported events. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield AssetMaterialization(
                    asset_key="my_dashboard",
                    metadata={
                        "dashboard_url": EventMetadata.url("http://mycoolsite.com/my_dashboard"),
                    }
                )


        Args:
            url (str): The URL for a metadata entry.
        """
        return UrlMetadataEntryData(url)

    @staticmethod
    def path(path: str) -> "PathMetadataEntryData":
        """Static constructor for a metadata value wrapping a path as
        :py:class:`PathMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata={
                        "filepath": EventMetadata.path("path/to/file"),
                    }
                )

        Args:
            path (str): The path for a metadata entry.
        """
        return PathMetadataEntryData(path)

    @staticmethod
    def json(data: Dict[str, Any]) -> "JsonMetadataEntryData":
        """Static constructor for a metadata value wrapping a path as
        :py:class:`JsonMetadataEntryData`. Can be used as the value type for the `metadata`
        parameter for supported events. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield ExpectationResult(
                    success=not missing_things,
                    label="is_present",
                    metadata={
                        "about my dataset": EventMetadata.json({"missing_columns": missing_things})
                    },
                )

        Args:
            data (Dict[str, Any]): The JSON data for a metadata entry.
        """
        return JsonMetadataEntryData(data)

    @staticmethod
    def md(data: str) -> "MarkdownMetadataEntryData":
        """Static constructor for a metadata value wrapping markdown data as
        :py:class:`MarkdownMetadataEntryData`. Can be used as the value type for the `metadata`
        parameter for supported events. For example:


        .. code-block:: python

            @op
            def emit_metadata(context, md_str):
                yield AssetMaterialization(
                    asset_key="info",
                    metadata={
                        'Details': EventMetadata.md(md_str)
                    },
                )

        Args:
            md_str (str): The markdown for a metadata entry.
        """
        return MarkdownMetadataEntryData(data)

    @staticmethod
    def python_artifact(python_artifact: Callable) -> "PythonArtifactMetadataEntryData":
        """Static constructor for a metadata value wrapping a python artifact as
        :py:class:`PythonArtifactMetadataEntryData`. Can be used as the value type for the
        `metadata` parameter for supported events. For example:

        .. code-block:: python

            @op
            def emit_metadata(context, df):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata={
                        "class": EventMetadata.python_artifact(MyClass),
                        "function": EventMetadata.python_artifact(my_function),
                    }
                )

        Args:
            value (Callable): The python class or function for a metadata entry.
        """
        check.callable_param(python_artifact, "python_artifact")
        return PythonArtifactMetadataEntryData(python_artifact.__module__, python_artifact.__name__)

    @staticmethod
    def float(value: float) -> "FloatMetadataEntryData":
        """Static constructor for a metadata value wrapping a float as
        :py:class:`FloatMetadataEntryData`. Can be used as the value type for the `metadata`
        parameter for supported events. For example:

        .. code-block:: python

            @op
            def emit_metadata(context, df):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata={
                        "size (bytes)": EventMetadata.float(calculate_bytes(df)),
                    }
                )

        Args:
            value (float): The float value for a metadata entry.
        """

        return FloatMetadataEntryData(value)

    @staticmethod
    def int(value: int) -> "IntMetadataEntryData":
        """Static constructor for a metadata value wrapping an int as
        :py:class:`IntMetadataEntryData`. Can be used as the value type for the `metadata`
        parameter for supported events. For example:

        .. code-block:: python

            @op
            def emit_metadata(context, df):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata={
                        "number of rows": EventMetadata.int(len(df)),
                    },
                )

        Args:
            value (int): The int value for a metadata entry.
        """

        return IntMetadataEntryData(value)

    @staticmethod
    def pipeline_run(run_id: str) -> "DagsterPipelineRunMetadataEntryData":
        check.str_param(run_id, "run_id")
        return DagsterPipelineRunMetadataEntryData(run_id)

    @staticmethod
    def dagster_run(run_id: str) -> "DagsterPipelineRunMetadataEntryData":
        return EventMetadata.pipeline_run(run_id)

    @staticmethod
    def asset(asset_key: "AssetKey") -> "DagsterAssetMetadataEntryData":
        """Static constructor for a metadata value referencing a Dagster asset, by key.

        For example:

        .. code-block:: python

            @op
            def validate_table(context, df):
                yield AssetMaterialization(
                    asset_key=AssetKey("my_table"),
                    metadata={
                        "Related asset": EventMetadata.asset(AssetKey('my_other_table')),
                    },
                )

        Args:
            asset_key (AssetKey): The asset key referencing the asset.
        """

        from dagster.core.definitions.events import AssetKey

        check.inst_param(asset_key, "asset_key", AssetKey)
        return DagsterAssetMetadataEntryData(asset_key)

    @staticmethod
    def table(data: List[Dict[str, object]]) -> "TableMetadataEntryData":
        """Static constructor for a metadata value wrapping arbitrary tabular data as
        :py:class:`TableMetadataEntryData`. Can be used as the value type for the `metadata`
        parameter for supported events. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield ExpectationResult(
                    success=not missing_things,
                    label="is_present",
                    metadata={
                        "about my dataset": EventMetadata.table([{"errors": 3}]),  # TODO: need better example
                    },
                )

        Args:
            data (str): The tabular data for a metadata entry.
        """
        return TableMetadataEntryData(data)

    @staticmethod
    def table_schema(
        schema: Dict[str, object],
    ) -> "TableSchemaMetadataEntryData":
        """Static constructor for a metadata value wrapping a table schema as
        :py:class:`TableSchemaMetadataEntryData`. Can be used as the value type
        for the `metadata` parameter for supported events. For example:

        .. code-block:: python

            schema = {
                "fields": [
                    { "name": "id", "type": "int" },
                    { "name": "status", "type": "bool" },
                ]
            },

            DagsterType(
                type_check_fn=some_validation_fn,
                name='MyTable',
                metadata={
                    "schema": EventMetadata.table_schema(schema),
                },
            )

        Args:
            schema (Dict): The table schema for a metadata entry.
        """
        return TableSchemaMetadataEntryData(schema)


@whitelist_for_serdes
class EventMetadataEntry(
    NamedTuple(
        "_EventMetadataEntry",
        [
            ("label", str),
            ("description", Optional[str]),
            ("entry_data", "EventMetadataEntryData"),
        ],
    )
):
    """The standard structure for describing metadata for Dagster events.

    Lists of objects of this type can be passed as arguments to Dagster events and will be displayed
    in Dagit and other tooling.

    Should be yielded from within an IO manager to append metadata for a given input/output event.
    For other event types, passing a dict with `EventMetadata` values to the `metadata` argument
    is preferred.

    Args:
        label (str): Short display label for this metadata entry.
        description (Optional[str]): A human-readable description of this metadata entry.
        entry_data (EventMetadataEntryData): Typed metadata entry data. The different types allow
            for customized display in tools like dagit.
    """

    def __new__(cls, label: str, description: Optional[str], entry_data: "EventMetadataEntryData"):
        return super(EventMetadataEntry, cls).__new__(
            cls,
            check.str_param(label, "label"),
            check.opt_str_param(description, "description"),
            check.inst_param(entry_data, "entry_data", EntryDataUnion),
        )

    @staticmethod
    def text(
        text: Optional[str], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing text as
        :py:class:`TextMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context, df):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata_entries=[
                        EventMetadataEntry.text("Text-based metadata for this event", "text_metadata")
                    ],
                )

        Args:
            text (Optional[str]): The text of this metadata entry.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """
        return EventMetadataEntry(label, description, TextMetadataEntryData(text))

    @staticmethod
    def url(
        url: Optional[str], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing a URL as
        :py:class:`UrlMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield AssetMaterialization(
                    asset_key="my_dashboard",
                    metadata_entries=[
                        EventMetadataEntry.url(
                            "http://mycoolsite.com/my_dashboard", label="dashboard_url"
                        ),
                    ],
                )

        Args:
            url (Optional[str]): The URL contained by this metadata entry.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """
        return EventMetadataEntry(label, description, UrlMetadataEntryData(url))

    @staticmethod
    def path(
        path: Optional[str], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing a path as
        :py:class:`PathMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata_entries=[EventMetadataEntry.path("path/to/file", label="filepath")],
                )

        Args:
            path (Optional[str]): The path contained by this metadata entry.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """
        return EventMetadataEntry(label, description, PathMetadataEntryData(path))

    @staticmethod
    def fspath(
        path: Optional[str], label: Optional[str] = None, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing a filesystem path as
        :py:class:`PathMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata_entries=[EventMetadataEntry.fspath("path/to/file")],
                )

        Args:
            path (Optional[str]): The path contained by this metadata entry.
            label (Optional[str]): Short display label for this metadata entry. Defaults to the
                base name of the path.
            description (Optional[str]): A human-readable description of this metadata entry.
        """
        if not label:
            path = cast(str, check.str_param(path, "path"))
            label = last_file_comp(path)

        return EventMetadataEntry.path(path, label, description)

    @staticmethod
    def json(
        data: Optional[Dict[str, Any]],
        label: str,
        description: Optional[str] = None,
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing JSON data as
        :py:class:`JsonMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield ExpectationResult(
                    success=not missing_things,
                    label="is_present",
                    metadata_entries=[
                        EventMetadataEntry.json(
                            label="metadata", data={"missing_columns": missing_things},
                        )
                    ],
                )

        Args:
            data (Optional[Dict[str, Any]]): The JSON data contained by this metadata entry.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """
        return EventMetadataEntry(label, description, JsonMetadataEntryData(data))

    @staticmethod
    def md(
        md_str: Optional[str], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing markdown data as
        :py:class:`MarkdownMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context, md_str):
                yield AssetMaterialization(
                    asset_key="info",
                    metadata_entries=[EventMetadataEntry.md(md_str=md_str)],
                )

        Args:
            md_str (Optional[str]): The markdown contained by this metadata entry.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """
        return EventMetadataEntry(label, description, MarkdownMetadataEntryData(md_str))

    @staticmethod
    def python_artifact(
        python_artifact: Callable[..., Any], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        check.callable_param(python_artifact, "python_artifact")
        return EventMetadataEntry(
            label,
            description,
            PythonArtifactMetadataEntryData(python_artifact.__module__, python_artifact.__name__),
        )

    @staticmethod
    def float(
        value: Optional[float], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing float as
        :py:class:`FloatMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context, df):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata_entries=[EventMetadataEntry.float(calculate_bytes(df), "size (bytes)")],
                )

        Args:
            value (Optional[float]): The float value contained by this metadata entry.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """

        return EventMetadataEntry(label, description, FloatMetadataEntryData(value))

    @staticmethod
    def int(
        value: Optional[int], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing int as
        :py:class:`IntMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context, df):
                yield AssetMaterialization(
                    asset_key="my_dataset",
                    metadata_entries=[EventMetadataEntry.int(len(df), "number of rows")],
                )

        Args:
            value (Optional[int]): The int value contained by this metadata entry.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """

        return EventMetadataEntry(label, description, IntMetadataEntryData(value))

    @staticmethod
    def pipeline_run(
        run_id: str, label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        check.str_param(run_id, "run_id")
        return EventMetadataEntry(label, description, DagsterPipelineRunMetadataEntryData(run_id))

    @staticmethod
    def asset(
        asset_key: "AssetKey", label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry referencing a Dagster asset, by key.

        For example:

        .. code-block:: python

            @op
            def validate_table(context, df):
                yield AssetMaterialization(
                    asset_key=AssetKey("my_table"),
                    metadata_entries=[
                         EventMetadataEntry.asset(AssetKey('my_other_table'), "Related asset"),
                    ],
                )

        Args:
            asset_key (AssetKey): The asset key referencing the asset.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """

        from dagster.core.definitions.events import AssetKey

        check.inst_param(asset_key, "asset_key", AssetKey)
        return EventMetadataEntry(label, description, DagsterAssetMetadataEntryData(asset_key))

    @staticmethod
    def table(
        data: List[Dict[str, object]], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":
        """Static constructor for a metadata entry containing tabluar data as
        :py:class:`TableMetadataEntryData`. For example:

        .. code-block:: python

            @op
            def emit_metadata(context):
                yield ExpectationResult(
                    success=no_failures,
                    label="is_valid",
                    metadata_entries=[
                        EventMetadataEntry.table(
                            data, label="failure_cases",
                        ),
                    ],
                )

        Args:
            data (List[Dict[str, object]]): The list of rows for the table.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """
        return EventMetadataEntry(label, description, TableMetadataEntryData(data))

    @staticmethod
    def table_schema(
        schema: Dict[str, object], label: str, description: Optional[str] = None
    ) -> "EventMetadataEntry":  # TODO fix docstring
        """Static constructor for a metadata entry containing a table schema as
        :py:class:`TableSchemaMetadataEntryData`. For example:

        .. code-block:: python

            schema = {
                "fields": [
                    { "name": "id", "type": "int" },
                    { "name": "status", "type": "bool" },
                ]
            },

            DagsterType(
                type_check_fn=some_validation_fn,
                name='MyTable',
                metadata_entries=[
                    EventMetadataEntry.table_schema(
                        schema,
                        label='schema',
                    )
                ]
            )

        Args:
            schema (Dict): The table schema for a metadata entry.
            label (str): Short display label for this metadata entry.
            description (Optional[str]): A human-readable description of this metadata entry.
        """
        return EventMetadataEntry(
            label,
            description,
            TableSchemaMetadataEntryData(schema),
        )


class PartitionMetadataEntry(
    NamedTuple(
        "_PartitionMetadataEntry",
        [
            ("partition", str),
            ("entry", "EventMetadataEntry"),
        ],
    )
):
    """Event containing an :py:class:`EventMetdataEntry` and the name of a partition that the entry
    applies to.

    This can be yielded or returned in place of EventMetadataEntries for cases where you are trying
    to associate metadata more precisely.
    """

    def __new__(cls, partition: str, entry: EventMetadataEntry):
        experimental_class_warning("PartitionMetadataEntry")
        return super(PartitionMetadataEntry, cls).__new__(
            cls,
            check.str_param(partition, "partition"),
            check.inst_param(entry, "entry", EventMetadataEntry),
        )
