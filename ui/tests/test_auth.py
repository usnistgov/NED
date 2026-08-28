from auth import _load_credentials


class TestLoadCredentials:
    def test_no_env_vars_returns_empty(self, monkeypatch):
        monkeypatch.delenv('APP_CREDENTIALS', raising=False)
        monkeypatch.delenv('APP_USERNAME', raising=False)
        monkeypatch.delenv('APP_PASSWORD', raising=False)
        assert _load_credentials() == {}

    def test_single_pair_from_app_credentials(self, monkeypatch):
        monkeypatch.setenv('APP_CREDENTIALS', 'alice:secret1')
        monkeypatch.delenv('APP_USERNAME', raising=False)
        monkeypatch.delenv('APP_PASSWORD', raising=False)
        assert _load_credentials() == {'alice': 'secret1'}

    def test_multiple_pairs_from_app_credentials(self, monkeypatch):
        monkeypatch.setenv('APP_CREDENTIALS', 'alice:secret1,bob:secret2')
        monkeypatch.delenv('APP_USERNAME', raising=False)
        monkeypatch.delenv('APP_PASSWORD', raising=False)
        assert _load_credentials() == {'alice': 'secret1', 'bob': 'secret2'}

    def test_pairs_are_trimmed_of_whitespace(self, monkeypatch):
        monkeypatch.setenv('APP_CREDENTIALS', ' alice:secret1 , bob:secret2 ')
        monkeypatch.delenv('APP_USERNAME', raising=False)
        monkeypatch.delenv('APP_PASSWORD', raising=False)
        assert _load_credentials() == {'alice': 'secret1', 'bob': 'secret2'}

    def test_malformed_pair_without_colon_is_skipped(self, monkeypatch):
        monkeypatch.setenv('APP_CREDENTIALS', 'alice-secret1,bob:secret2')
        monkeypatch.delenv('APP_USERNAME', raising=False)
        monkeypatch.delenv('APP_PASSWORD', raising=False)
        assert _load_credentials() == {'bob': 'secret2'}

    def test_pair_with_missing_password_is_skipped(self, monkeypatch):
        monkeypatch.setenv('APP_CREDENTIALS', 'alice:,bob:secret2')
        monkeypatch.delenv('APP_USERNAME', raising=False)
        monkeypatch.delenv('APP_PASSWORD', raising=False)
        assert _load_credentials() == {'bob': 'secret2'}

    def test_legacy_username_password_vars(self, monkeypatch):
        monkeypatch.delenv('APP_CREDENTIALS', raising=False)
        monkeypatch.setenv('APP_USERNAME', 'legacy_user')
        monkeypatch.setenv('APP_PASSWORD', 'legacy_pass')
        assert _load_credentials() == {'legacy_user': 'legacy_pass'}

    def test_legacy_vars_do_not_override_app_credentials_same_user(
        self, monkeypatch
    ):
        monkeypatch.setenv('APP_CREDENTIALS', 'alice:secret1')
        monkeypatch.setenv('APP_USERNAME', 'alice')
        monkeypatch.setenv('APP_PASSWORD', 'legacy_pass')
        assert _load_credentials() == {'alice': 'secret1'}

    def test_legacy_vars_combine_with_app_credentials_different_user(
        self, monkeypatch
    ):
        monkeypatch.setenv('APP_CREDENTIALS', 'alice:secret1')
        monkeypatch.setenv('APP_USERNAME', 'bob')
        monkeypatch.setenv('APP_PASSWORD', 'legacy_pass')
        assert _load_credentials() == {
            'alice': 'secret1',
            'bob': 'legacy_pass',
        }

    def test_legacy_vars_require_both_username_and_password(self, monkeypatch):
        monkeypatch.delenv('APP_CREDENTIALS', raising=False)
        monkeypatch.setenv('APP_USERNAME', 'legacy_user')
        monkeypatch.delenv('APP_PASSWORD', raising=False)
        assert _load_credentials() == {}
