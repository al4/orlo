from __future__ import print_function, unicode_literals
from datetime import datetime, timedelta
import orlo
import json
import uuid
import unittest
from flask.ext.testing import TestCase
from orlo.orm import db, Package, Release
from orlo.config import config


class OrloTest(TestCase):
    """
    Base class for tests which contains the methods required to move
    releases and packages through the workflow
    """

    def create_app(self):
        app = orlo.app
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        app.config['TESTING'] = True
        app.config['DEBUG'] = True
        app.config['TRAP_HTTP_EXCEPTIONS'] = True
        app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = False

        return orlo.app

    def setUp(self):
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def _create_release(self,
                        user='testuser',
                        team='test team',
                        platforms='test_platform',
                        references='TestTicket-123',
                        ):
        """
        Create a release using the REST API

        :param user:
        :param team:
        :param platforms:
        :param references:
        :return: the release ID
        """

        response = self.client.post(
            '/releases',
            data=json.dumps({
                'note': 'test note lorem ipsum',
                'platforms': platforms,
                'references': references,
                'team': team,
                'user': user,
            }),
            content_type='application/json',
        )
        self.assert200(response)
        return response.json['id']

    def _create_package(self, release_id,
                        name='test-package',
                        version='1.2.3',
                        diff_url=None,
                        rollback=False,
                        ):
        """
        Create a package using the REST API

        :param release_id: release id to create the package for
        :param name:
        :param version:
        :param diff_url:
        :param rollback:
        :return: package id
        """
        doc = {
            'name': name,
            'version': version,
        }

        if diff_url:
            doc['diff_url'] = diff_url
        if rollback:
            doc['rollback'] = rollback

        response = self.client.post(
            '/releases/{}/packages'.format(release_id),
            data=json.dumps(doc),
            content_type='application/json',
        )
        self.assert200(response)
        return response.json['id']

    def _start_package(self, release_id, package_id):
        """
        Start a package using the REST API

        :param release_id:
        :return:
        """

        response = self.client.post(
            '/releases/{}/packages/{}/start'.format(release_id, package_id),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        return response

    def _stop_package(self, release_id, package_id,
                      success=True):
        """
        Start a package using the REST API

        :param release_id:
        :return:
        """

        response = self.client.post(
            '/releases/{}/packages/{}/stop'.format(release_id, package_id),
            data=json.dumps({
                'success': str(success),
                'foo': 'bar',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        return response

    def _stop_release(self, release_id):
        """
        Stop a release using the REST API

        :param release_id:
        :return:
        """
        response = self.client.post(
            '/releases/{}/stop'.format(release_id),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 204)
        return response

    def _create_finished_release(self):
        """
        Create a completed release, with default values, that has gone through
        the whole workflow
        """
        release_id = self._create_release()
        package_id = self._create_package(release_id)

        self._start_package(release_id, package_id)
        self._stop_package(release_id, package_id)
        self._stop_release(release_id)

        return release_id

    def _post_releases_notes(self, release_id, text):
        """
        Add a note to a release
        """

        doc = {'text': text}
        response = self.client.post(
            '/releases/{}/notes'.format(release_id, text),
            data=json.dumps(doc),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        return response


class PostContractTest(OrloTest):
    """
    Test the HTTP POST contract
    """

    def test_create_release(self):
        """
        Create a release
        """
        release_id = self._create_release()
        self.assertEqual(uuid.UUID(release_id).get_version(), 4)

    def test_create_package(self):
        """
        Create a package
        """
        release_id = self._create_release()
        package_id = self._create_package(release_id)
        self.assertEqual(uuid.UUID(package_id).get_version(), 4)

    def test_add_results(self):
        """
        Add the results of a package deploy
        """
        release_id = self._create_release()
        package_id = self._create_package(release_id)

        results_response = self.client.post(
            '/releases/{}/packages/{}/results'.format(
                release_id, package_id),
            data=json.dumps({
                'success': 'true',
                'foo': 'bar',
            }),
            content_type='application/json',
        )
        self.assertEqual(results_response.status_code, 204)

    def test_package_start(self):
        """
        Test starting a package
        """
        release_id = self._create_release()
        package_id = self._create_package(release_id)

        return release_id, package_id

    def test_package_stop(self):
        """
        Test stopping a package
        """
        release_id = self._create_release()
        package_id = self._create_package(release_id)
        self._start_package(release_id, package_id)
        self._stop_package(release_id, package_id)

    def test_release_stop(self):
        """
        Test stopping a release

        As before, calls all the others as we need a full workflow present
        """
        release_id = self._create_release()
        package_id = self._create_package(release_id)
        self._start_package(release_id, package_id)
        self._stop_package(release_id, package_id)
        self._stop_release(release_id)

    def test_post_note(self):
        """
        Test adding a release
        """
        release_id = self._create_release()
        response = self._post_releases_notes(release_id, "this is a test message")
        self.assertEqual(204, response.status_code)

    def test_create_release_minimal(self):
        """
        Create a release, omitting all optional parameters
        """
        response = self.client.post('/releases',
            data=json.dumps({
                'platforms': ['test_platform'],
                'user': 'testuser',
            }),
            content_type='application/json',
        )
        self.assert200(response)

    def test_diffurl_present(self):
        """
        Test that the diff_url parameter is stored
        """
        test_url = 'http://example.com'

        release_id = self._create_release()
        package_id = self._create_package(release_id, diff_url=test_url)

        q = db.session.query(Package).filter(Package.id == package_id)
        pkg = q.first()
        self.assertEqual(pkg.diff_url, test_url)

    def test_rollback_present(self):
        """
        Test that that rollback parameter is stored
        """
        release_id = self._create_release()
        package_id = self._create_package(release_id, rollback=True)

        q = db.session.query(Package).filter(Package.id == package_id)
        pkg = q.first()

        self.assertEqual(pkg.rollback, True)

    def test_references_json_conversion(self):
        """
        Test that the references parameter results in valid json in the database
        """
        release_id = self._create_release(references=['ticket1', 'ticket2'])
        q = db.session.query(Release).filter(Release.id == release_id)
        release = q.first()

        doc = json.loads(release.references)
        self.assertIsInstance(doc, list)


class GetContractTest(OrloTest):
    """
    Test the HTTP GET contract
    """

    def _get_releases(self, release_id=None, filters=None):
        """
        Perform a GET to /releases with optional filters
        """

        if release_id:
            path = '/releases/{}'.format(release_id)
        elif filters:
            path = '/releases?{}'.format('&'.join(filters))
        else:
            path = '/releases'

        print("GET {}".format(path))
        results_response = self.client.get(
            path, content_type='application/json',
        )
        self.assertEqual(results_response.status_code, 200)
        r_json = json.loads(results_response.data)
        return r_json

    def test_ping(self):
        """
        Start with something simple
        """
        response = self.client.get('/ping')
        self.assert200(response)
        self.assertEqual(response.data, 'pong')

    def test_get_single_release(self):
        """
        Fetch a single release
        """
        release_id = self._create_release()
        r = self._get_releases(release_id=release_id)

        self.assertEqual(1, len(r['releases']))
        self.assertEqual(release_id, r['releases'][0]['id'])

    def test_get_releases(self):
        """
        Test the list of releases
        """
        for _ in range(0, 3):
            self._create_finished_release()
        results = self._get_releases()
        self.assertEqual(len(results['releases']), 3)

    def test_get_release_filter_package(self):
        """
        Filter on releases that contain a package
        """
        for _ in range(0, 3):
            self._create_finished_release()

        release_id = self._create_release()
        package_id = self._create_package(release_id, name='specific-package')
        results = self._get_releases(filters=[
            'package_name=specific-package'
            ])

        for r in results['releases']:
            for p in r['packages']:
                self.assertEqual(p['name'], 'specific-package')
                self.assertEqual(p['id'], package_id)

        self.assertEqual(len(results['releases']), 1)

    def test_get_release_filter_user(self):
        """
        Filter on releases that were performed by a user
        """
        for _ in range(0, 3):
            self._create_release(user='firstUser')

        for _ in range(0, 2):
            self._create_release(user='secondUser')

        first_results = self._get_releases(filters=['user=firstUser'])
        second_results = self._get_releases(filters=['user=secondUser'])

        self.assertEqual(len(first_results['releases']), 3)
        self.assertEqual(len(second_results['releases']), 2)

        for r in first_results['releases']:
            self.assertEqual(r['user'], 'firstUser')
        for r in second_results['releases']:
            self.assertEqual(r['user'], 'secondUser')

    def test_get_release_filter_platform(self):
        """
        Filter on releases that were on a particular platform
        """
        for _ in range(0, 3):
            self._create_release(platforms='firstPlatform')

        for _ in range(0, 2):
            self._create_release(platforms=['firstPlatform', 'secondPlatform'])

        first_results = self._get_releases(filters=['platform=firstPlatform'])
        second_results = self._get_releases(filters=['platform=secondPlatform'])

        # Should be all releases
        self.assertEqual(len(first_results['releases']), 5)
        # Just those that contain "secondPlatform"
        self.assertEqual(len(second_results['releases']), 2)

        for r in first_results['releases']:
            self.assertIn('firstPlatform', r['platforms'])
        for r in second_results['releases']:
            self.assertIn('secondPlatform', r['platforms'])

    def _get_releases_time_filter(self, field, finished=False):
        """
        Return releases given the time-based filter field

        Abstracts a bit of common code in the stime/ftime tests
        """
        for _ in range(0, 3):
            if finished:
                self._create_finished_release()
            else:
                self._create_release()

        t_format = config.get('main', 'time_format')
        now = datetime.utcnow()

        yesterday = (now - timedelta(days=1)).strftime(t_format)
        tomorrow = (now + timedelta(days=1)).strftime(t_format)

        r_yesterday = self._get_releases(filters=['{}={}'.format(field, yesterday)])
        r_tomorrow = self._get_releases(filters=['{}={}'.format(field, tomorrow)])

        return r_yesterday, r_tomorrow

    def test_get_release_filter_stime_before(self):
        """
        Filter on releases that started before a particular time
        """
        r_yesterday, r_tomorrow = self._get_releases_time_filter('stime_before')

        self.assertEqual(3, len(r_tomorrow['releases']))
        self.assertEqual(0, len(r_yesterday['releases']))

    def test_get_release_filter_stime_after(self):
        """
        Filter on releases that started after a particular time
        """
        r_yesterday, r_tomorrow = self._get_releases_time_filter('stime_after')

        self.assertEqual(0, len(r_tomorrow['releases']))
        self.assertEqual(3, len(r_yesterday['releases']))

    def test_get_release_filter_ftime_before(self):
        """
        Filter on releases that finished before a particular time
        """
        r_yesterday, r_tomorrow = self._get_releases_time_filter(
            'ftime_before', finished=True)

        self.assertEqual(3, len(r_tomorrow['releases']))
        self.assertEqual(0, len(r_yesterday['releases']))

    def test_get_release_filter_ftime_after(self):
        """
        Filter on releases that finished after a particular time
        """
        r_yesterday, r_tomorrow = self._get_releases_time_filter(
            'ftime_after', finished=True)

        self.assertEqual(0, len(r_tomorrow['releases']))
        self.assertEqual(3, len(r_yesterday['releases']))

    def test_get_release_filter_duration_lt(self):
        """
        Filter on releases that took less than x seconds

        All releases take a very small amount of time in our tests,
        but all should be <10 and >0 at least!
        """
        for _ in range(0, 3):
            self._create_finished_release()

        r = self._get_releases(filters=['duration_lt=10'])
        self.assertEqual(3, len(r['releases']))

        r = self._get_releases(filters=['duration_lt=0'])
        self.assertEqual(0, len(r['releases']))

    def test_get_release_filter_duration_gt(self):
        """
        Filter on releases that took greater than x seconds
        """
        for _ in range(0, 3):
            self._create_finished_release()

        r = self._get_releases(filters=['duration_gt=10'])
        self.assertEqual(0, len(r['releases']))

        r = self._get_releases(filters=['duration_gt=0'])
        self.assertEqual(3, len(r['releases']))

    def test_get_release_filter_team(self):
        """
        Filter on releases that a team was responsible for
        """
        for _ in range(0, 3):
            self._create_release(team='firstTeam')

        for _ in range(0, 2):
            self._create_release(team='secondTeam')

        first_results = self._get_releases(filters=['team=firstTeam'])
        second_results = self._get_releases(filters=['team=secondTeam'])

        self.assertEqual(len(first_results['releases']), 3)
        self.assertEqual(len(second_results['releases']), 2)

        for r in first_results['releases']:
            self.assertEqual(r['team'], 'firstTeam')
        for r in second_results['releases']:
            self.assertEqual(r['team'], 'secondTeam')

    def test_get_release_filter_rollback(self):
        """
        Filter on releases that contain a rollback
        """
        for _ in range(0, 3):
            rid = self._create_release()
            self._create_package(rid, rollback=True)

        for _ in range(0, 2):
            rid = self._create_release()
            self._create_package(rid, rollback=False)

        first_results = self._get_releases(filters=['package_rollback=True'])
        second_results = self._get_releases(filters=['package_rollback=False'])

        self.assertEqual(len(first_results['releases']), 3)
        self.assertEqual(len(second_results['releases']), 2)

        for r in first_results['releases']:
            for p in r['packages']:
                self.assertIs(p['rollback'], True)
        for r in second_results['releases']:
            for p in r['packages']:
                self.assertIs(p['rollback'], False)

    def test_get_release_first(self):
        """
        Should return only one release
        """

        for _ in range(0, 3):
            rid = self._create_release()

        r = self._get_releases(filters=['latest=True'])
        self.assertEqual(len(r['releases']), 1)

    def test_get_release_package_name(self):
        """
        Filter on releases which have a particular package name
        """
        rid = self._create_release()
        self._create_package(rid, name='particular-name')
        self._create_package(rid, name='another-name')

        rid2 = self._create_release()
        self._create_package(rid2, name='another-name')

        r = self._get_releases(filters=['package_name=particular-name'])
        self.assertEqual(len(r['releases']), 1)

    def test_get_release_package_version(self):
        """
        Filter on releases which have a particular version
        """
        rid = self._create_release()
        self._create_package(rid, version='4.9.9')
        self._create_package(rid, version='3.5.6')

        rid2 = self._create_release()
        self._create_package(rid2, version='1.2.3')

        r = self._get_releases(filters=['package_version=4.9.9'])
        self.assertEqual(len(r['releases']), 1)

    def test_get_release_package_status_not_started(self):
        """
        Filter on releases which have package status NOT_STARTED
        """
        rid = self._create_release()
        self._create_package(rid)

        self._create_release()  # extra, should be filtered out

        r = self._get_releases(filters=['package_status=NOT_STARTED'])
        self.assertEqual(len(r['releases']), 1)

    def test_get_release_package_status_in_progress(self):
        """
        Filter on releases which have package status IN_PROGRESS
        """
        rid = self._create_release()
        pid = self._create_package(rid)
        self._start_package(rid, pid)

        self._create_release()  # extra, should be filtered out

        r = self._get_releases(filters=['package_status=IN_PROGRESS'])
        self.assertEqual(len(r['releases']), 1)

    def test_get_release_package_status_successful(self):
        """
        Filter on releases which have package status SUCCESSFUL
        """
        rid = self._create_release()
        pid = self._create_package(rid)
        self._start_package(rid, pid)
        self._stop_package(rid, pid, success=True)

        self._create_release()  # extra, should be filtered out

        r = self._get_releases(filters=['package_status=SUCCESSFUL'])
        self.assertEqual(len(r['releases']), 1)

    def test_get_release_package_status_failed(self):
        """
        Filter on releases which have package status FAILED
        """
        rid = self._create_release()
        pid = self._create_package(rid)
        self._start_package(rid, pid)
        self._stop_package(rid, pid, success=False)

        self._create_release()  # extra, should be filtered out

        r = self._get_releases(filters=['package_status=FAILED'])
        self.assertEqual(len(r['releases']), 1)

    def test_get_release_package_duration_gt(self):
        """
        Filter on releases with a package of duration greater than X
        """
        rid = self._create_release()
        pid = self._create_package(rid)
        self._start_package(rid, pid)
        self._stop_package(rid, pid, success=False)

        r = self._get_releases(filters=['package_duration_gt=0'])
        self.assertEqual(len(r['releases']), 1)

    def test_get_release_package_duration_lt(self):
        """
        Filter on releases with a package of duration less than X
        """
        rid = self._create_release()
        pid = self._create_package(rid)
        self._start_package(rid, pid)
        self._stop_package(rid, pid, success=False)

        r = self._get_releases(filters=['package_duration_lt=10'])
        self.assertEqual(len(r['releases']), 1)

        # TODO need control release

    def test_get_release_filter_rollback_and_status(self):
        """
        Filter on rollback and status
        """
        for _ in range(0, 3):
            rid = self._create_release()
            self._create_package(rid, rollback=True)

        for _ in range(0, 2):
            rid = self._create_release()
            self._create_package(rid, rollback=False)

        first_results = self._get_releases(filters=['package_rollback=True',
                                                    'package_status=NOT_STARTED'])
        second_results = self._get_releases(filters=['package_rollback=False',
                                                     'package_status=NOT_STARTED'])
        # should be zero
        third_results = self._get_releases(filters=['package_rollback=FALSE',
                                                    'package_status=SUCCESSFUL'])

        self.assertEqual(len(first_results['releases']), 3)
        self.assertEqual(len(second_results['releases']), 2)
        self.assertEqual(len(third_results['releases']), 0)

        for r in first_results['releases']:
            for p in r['packages']:
                self.assertIs(p['rollback'], True)
        for r in second_results['releases']:
            for p in r['packages']:
                self.assertIs(p['rollback'], False)
