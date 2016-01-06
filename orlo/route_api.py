from orlo import app, queries
from orlo.exceptions import InvalidUsage
from flask import jsonify, request, Response, json
import arrow
import datetime
from orlo.orm import db, Release, Package, PackageResult, ReleaseNote, Platform
from orlo.util import validate_request_json, create_release, validate_release_input, \
    validate_package_input, fetch_release, create_package, fetch_package, stream_json_list


@app.route('/ping', methods=['GET'])
def ping():
    """
    Simple ping test, takes no parameters

    **Example curl**:

    .. sourcecode:: shell

        curl -X GET 'http://127.0.0.1/ping'
    """
    return 'pong'


@app.route('/releases', methods=['POST'])
def post_releases():
    """
    Create a release - the first step in a deployment

    :<json string user: User that is performing the release
    :<json string team: The development team responsible for this release
    :<json array platforms: List of platforms receiving the release
    :<json array references: List of external references, e.g. Jira ticket
    :>json string id: UUID reference to the created release
    :reqheader Content-Type: Must be application/json
    :status 200: Release was created successfully
    :status 400: Invalid request

    **Example curl**:

    .. sourcecode:: shell

        curl -H "Content-Type: application/json" \\
        -X POST \\
        http://127.0.0.1/releases \\
        -d '{"note": "blah", "platforms": ["site1"], "references": ["ticket"], "team": "A-Team",
        "user": "aforbes"}'
    """
    validate_release_input(request)
    release = create_release(request)

    if request.json.get('note'):
        release_note = ReleaseNote(release.id, request.json.get('note'))
        db.session.add(release_note)

    app.logger.info(
            'Create release {}, references: {}, platforms: {}'.format(
                    release.id, release.notes, release.references, release.platforms)
    )

    release.start()

    db.session.add(release)
    db.session.commit()

    return jsonify(id=release.id)


@app.route('/releases/<release_id>/packages', methods=['POST'])
def post_packages(release_id):
    """
    Add a package to a release

    :param string release_id: UUID of the release to add the package to
    :<json string name: Name of the package
    :<json string version: Version of the package
    :<json boolean rollback: Whether this package deploy is a rollback
    :>json string id: UUID reference to the created package
    :reqheader Content-Type: Must be application/json
    :status 200: Package was added to the release successfully
    :status 400: Invalid request
    **Example curl**:

    .. sourcecode:: shell

        curl -H "Content-Type: application/json" \\
        -X POST \\
        http://127.0.0.1/releases/${RELEASE_ID}/packages \\
        -d '{"name": "test-package", "version": "1.0.1"}'
    """
    validate_package_input(request, release_id)

    release = fetch_release(release_id)
    package = create_package(release.id, request)

    app.logger.info(
            'Create package {}, release {}, name {}, version {}'.format(
                    package.id, release.id, request.json['name'],
                    request.json['version']))

    db.session.add(package)
    db.session.commit()

    return jsonify(id=package.id)


@app.route('/releases/<release_id>/packages/<package_id>/results',
           methods=['POST'])
def post_results(release_id, package_id):
    """
    Post the results of a package release

    :param string release_id: Release UUID
    :param string package_id: Package UUID
    :<json string content: Free text field to store what you wish
    :status 204: Package results added successfully
    """
    results = PackageResult(package_id, str(request.json))
    app.logger.info("Post results, release {}, package {}".format(
            release_id, package_id))
    db.session.add(results)
    db.session.commit()
    return '', 204


@app.route('/releases/<release_id>/stop', methods=['POST'])
def post_releases_stop(release_id):
    """
    Indicate that a release has finished

    This should be called after all packages have also been "stopped".
    In future it may stop any un-stopped packages.

    :param string release_id: Release UUID

    **Example curl**:

    .. sourcecode:: shell

        curl -H "Content-Type: application/json" \\
        -X POST http://127.0.0.1/releases/${RELEASE_ID}/stop
    """
    release = fetch_release(release_id)
    # TODO check that all packages have been finished
    app.logger.info("Release stop, release {}".format(release_id))
    release.stop()

    db.session.add(release)
    db.session.commit()
    return '', 204


@app.route('/releases/<release_id>/packages/<package_id>/start',
           methods=['POST'])
def post_packages_start(release_id, package_id):
    """
    Indicate that a package has started deploying

    :param string release_id: Release UUID
    :param string package_id: Package UUID
    :status 204:

    **Example curl**:

    .. sourcecode:: shell

        curl -X POST http://127.0.0.1/releases/${RELEASE_ID}/packages/${PACKAGE_ID}/start
    """
    package = fetch_package(release_id, package_id)
    app.logger.info("Package start, release {}, package {}".format(
            release_id, package_id))
    package.start()

    db.session.add(package)
    db.session.commit()
    return '', 204


@app.route('/releases/<release_id>/packages/<package_id>/stop',
           methods=['POST'])
def post_packages_stop(release_id, package_id):
    """
    Indicate that a package has finished deploying

    **Example curl**:

    .. sourcecode:: shell

        curl -H "Content-Type: application/json" \\
        -X POST http://127.0.0.1/releases/${RELEASE_ID}/packages/${PACKAGE_ID}/stop \\
        -d '{"success": "true"}'

    :param string package_id: Package UUID
    :param string release_id: Release UUID
    """
    validate_request_json(request)
    success = request.json.get('success') in ['True', 'true', '1']

    package = fetch_package(release_id, package_id)
    app.logger.info("Package stop, release {}, package {}, success {}".format(
            release_id, package_id, success))
    package.stop(success=success)

    db.session.add(package)
    db.session.commit()
    return '', 204


@app.route('/releases/<release_id>/notes', methods=['POST'])
def post_releases_notes(release_id):
    """
    Add a note to a release

    :param string release_id: Release UUID
    :query string text: Text
    :return:
    """
    validate_request_json(request)
    text = request.json.get('text')
    if not text:
        raise InvalidUsage("Must include text in posted document")

    note = ReleaseNote(release_id, text)
    app.logger.info("Adding note to release {}".format(release_id))
    db.session.add(note)
    db.session.commit()
    return '', 204


@app.route('/releases', methods=['GET'])
@app.route('/releases/<release_id>', methods=['GET'])
def get_releases(release_id=None):
    """
    Return a list of releases to the client, filters optional

    :param string release_id: Optionally specify a single release UUID to fetch. \
        This does not disable filters.
    :query boolean latest: Return only the last matching release (the latest)
    :query string package_name: Filter releases by package name
    :query string user: Filter releases by user the that performed the release
    :query string platform: Filter releases by platform
    :query string stime_before: Only include releases that started before timestamp given
    :query string stime_after: Only include releases that started after timestamp given
    :query string ftime_before: Only include releases that finished before timestamp given
    :query string ftime_after: Only include releases that finished after timestamp given
    :query string team: Filter releases by team
    :query int duration_lt: Only include releases that took less than (int) seconds
    :query int duration_gt: Only include releases that took more than (int) seconds
    :query boolean package_rollback: Filter on whether or not the releases contain a rollback
    :query string package_name: Filter by package name
    :query string package_version: Filter by package version
    :query int package_duration_gt: Filter by packages of duration greater than
    :query int package_duration_lt: Filter by packages of duration less than
    :query string package_status: Filter by package status. Valid statuses are:\
         "NOT_STARTED", "IN_PROGRESS", "SUCCESSFUL", "FAILED"

    **Note for time arguments**:
        The timestamp format you must use is specified in /etc/orlo.conf. All times are UTC.

    """

    if release_id:  # Simple
        query = db.session.query(Release).filter(Release.id == release_id)
    else:  # Bit more complex
        # Flatten args, as the ImmutableDict puts some values in a list when expanded
        args = {}
        for k, v in request.args.items():
            if type(v) is list:
                args[k] = v[0]
            else:
                args[k] = v
        query = queries.releases(**args)

    return Response(stream_json_list('releases', query), content_type='application/json')
