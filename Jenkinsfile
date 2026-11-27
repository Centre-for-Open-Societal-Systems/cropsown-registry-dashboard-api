// Validation only. Image publication and deployment belong to the registry.
// load needs a workspace, so check out inside a node and run the pipeline after it.
def checks
node {
    checkout scm
    checks = load('ci/pipelines/checks.groovy')
}
checks.call()
