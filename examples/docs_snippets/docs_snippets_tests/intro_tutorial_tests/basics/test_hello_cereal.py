from docs_snippets.intro_tutorial.basics.single_solid_pipeline.hello_cereal import hello_cereal_job
from docs_snippets.intro_tutorial.test_util import patch_cereal_requests


@patch_cereal_requests
def test_tutorial_intro_tutorial_hello_world():
    result = hello_cereal_job.execute_in_process()
    assert result.success
