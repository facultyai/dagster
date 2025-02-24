import pytest
import responses
from dagster import Failure, MetadataEntry, build_init_resource_context
from dagster_airbyte import AirbyteOutput, AirbyteState, airbyte_resource
from dagster_airbyte.utils import generate_materializations


@responses.activate
def test_trigger_connection():
    ab_resource = airbyte_resource(
        build_init_resource_context(
            config={
                "host": "some_host",
                "port": "8000",
            }
        )
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/sync",
        json={"job": {"id": 1}},
        status=200,
    )
    resp = ab_resource.start_sync("some_connection")
    assert resp == {"job": {"id": 1}}


def test_trigger_connection_fail():
    ab_resource = airbyte_resource(
        build_init_resource_context(config={"host": "some_host", "port": "8000"})
    )
    with pytest.raises(Failure, match="Exceeded max number of retries"):
        ab_resource.sync_and_poll("some_connection")


@responses.activate
@pytest.mark.parametrize(
    "state",
    [AirbyteState.SUCCEEDED, AirbyteState.CANCELLED, AirbyteState.ERROR, "unrecognized"],
)
def test_sync_and_poll(state):
    ab_resource = airbyte_resource(
        build_init_resource_context(
            config={
                "host": "some_host",
                "port": "8000",
            }
        )
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/get",
        json={"name": "some_connection"},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/sync",
        json={"job": {"id": 1}},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={"job": {"id": 1, "status": state}},
        status=200,
    )

    if state == AirbyteState.ERROR:
        with pytest.raises(Failure, match="Job failed"):
            r = ab_resource.sync_and_poll("some_connection", 0)

    elif state == AirbyteState.CANCELLED:
        with pytest.raises(Failure, match="Job was cancelled"):
            r = ab_resource.sync_and_poll("some_connection", 0)

    elif state == "unrecognized":
        with pytest.raises(Failure, match="unexpected state"):
            r = ab_resource.sync_and_poll("some_connection", 0)

    else:
        r = ab_resource.sync_and_poll("some_connection", 0)
        assert r == AirbyteOutput({"job": {"id": 1, "status": state}}, {"name": "some_connection"})


@responses.activate
def test_logging_multi_attempts(capsys):
    def _get_attempt(ls):
        return {"logs": {"logLines": ls}}

    ab_resource = airbyte_resource(
        build_init_resource_context(
            config={
                "host": "some_host",
                "port": "8000",
            }
        )
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/get",
        json={},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/sync",
        json={"job": {"id": 1}},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={"job": {"id": 1, "status": "pending"}},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={
            "job": {"id": 1, "status": "running"},
            "attempts": [_get_attempt(ls) for ls in [["log1a"]]],
        },
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={
            "job": {"id": 1, "status": "running"},
            "attempts": [_get_attempt(ls) for ls in [["log1a", "log1b"]]],
        },
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={
            "job": {"id": 1, "status": "running"},
            "attempts": [
                _get_attempt(ls) for ls in [["log1a", "log1b", "log1c"], ["log2a", "log2b"]]
            ],
        },
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={
            "job": {"id": 1, "status": AirbyteState.SUCCEEDED},
            "attempts": [
                _get_attempt(ls) for ls in [["log1a", "log1b", "log1c"], ["log2a", "log2b"]]
            ],
        },
        status=200,
    )
    ab_resource.sync_and_poll("some_connection", 0, None)
    captured = capsys.readouterr()
    assert captured.out == "\n".join(["log1a", "log1b", "log1c", "log2a", "log2b"]) + "\n"


@responses.activate
def test_assets():

    ab_resource = airbyte_resource(
        build_init_resource_context(
            config={
                "host": "some_host",
                "port": "8000",
            }
        )
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/get",
        json={
            "name": "xyz",
            "syncCatalog": {
                "streams": [
                    {
                        "stream": {
                            "name": "foo",
                            "jsonSchema": {
                                "properties": {"a": {"type": "str"}, "b": {"type": "int"}}
                            },
                        },
                        "config": {"selected": True},
                    },
                    {
                        "stream": {
                            "name": "bar",
                            "jsonSchema": {
                                "properties": {
                                    "c": {"type": "str"},
                                }
                            },
                        },
                        "config": {"selected": True},
                    },
                    {
                        "stream": {
                            "name": "baz",
                            "jsonSchema": {
                                "properties": {
                                    "d": {"type": "str"},
                                }
                            },
                        },
                        "config": {"selected": False},
                    },
                ]
            },
        },
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/sync",
        json={"job": {"id": 1}},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={
            "job": {"id": 1, "status": AirbyteState.SUCCEEDED},
            "attempts": [
                {
                    "attempt": {
                        "streamStats": [
                            {
                                "streamName": "foo",
                                "stats": {
                                    "bytesEmitted": 1234,
                                    "recordsCommitted": 4321,
                                },
                            },
                            {
                                "streamName": "bar",
                                "stats": {
                                    "bytesEmitted": 1234,
                                    "recordsCommitted": 4321,
                                },
                            },
                        ]
                    }
                }
            ],
        },
        status=200,
    )

    airbyte_output = ab_resource.sync_and_poll("some_connection", 0, None)

    materializations = list(generate_materializations(airbyte_output, []))
    assert len(materializations) == 2

    assert MetadataEntry.text("a,b", "columns") in materializations[0].metadata_entries
    assert MetadataEntry.int(1234, "bytesEmitted") in materializations[0].metadata_entries
    assert MetadataEntry.int(4321, "recordsCommitted") in materializations[0].metadata_entries


@responses.activate
def test_sync_and_poll_timeout():
    ab_resource = airbyte_resource(
        build_init_resource_context(
            config={
                "host": "some_host",
                "port": "8000",
            }
        )
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/get",
        json={},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/connections/sync",
        json={"job": {"id": 1}},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={"job": {"id": 1, "status": "pending"}},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={"job": {"id": 1, "status": "running"}},
        status=200,
    )
    responses.add(
        method=responses.POST,
        url=ab_resource.api_base_url + "/jobs/get",
        json={"job": {"id": 1, "status": "running"}},
        status=200,
    )
    poll_wait_second = 2
    timeout = 1
    with pytest.raises(Failure, match="Timeout: Airbyte job"):
        ab_resource.sync_and_poll("some_connection", poll_wait_second, timeout)
