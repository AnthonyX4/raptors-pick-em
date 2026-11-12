from conftest import register_and_login

# a token carries only the user id ({"sub": "<user_id>"}) and stays validly signed until it expires,
# so what it resolves to depends entirely on which row holds that id when the request arrives


def me(client, headers):
    return client.get("/api/users/me", headers=headers).json()


def test_token_stops_working_once_the_account_is_deleted(client, user_headers):
    user_id = me(client, user_headers)["user_id"]

    assert client.delete(f"/api/users/{user_id}", headers=user_headers).status_code == 204

    # the token is still unexpired and correctly signed, there's just no row for it to resolve to
    assert client.get("/api/users/me", headers=user_headers).status_code == 401


def test_a_new_account_never_inherits_a_deleted_users_id(client, user_headers):
    # sqlite hands out "largest id in the table + 1", so without AUTOINCREMENT the next signup
    # would take the deleted user's id and their old token would authenticate as the new account
    deleted_id = me(client, user_headers)["user_id"]
    assert client.delete(f"/api/users/{deleted_id}", headers=user_headers).status_code == 204

    newcomer_headers = register_and_login(client, "newcomer@example.com")

    assert me(client, newcomer_headers)["user_id"] != deleted_id
    assert client.get("/api/users/me", headers=user_headers).status_code == 401 # the old token still reaches nobody
