import user

if __name__ == "__main__":
    # Example usage
    username = "Main_Admin"
    password = "qwertzuiopasdfghjkl"
    # Add a new user
    added = user.add_user(username, password)
    print(f"User {username} added: {added}")
    user.make_admin(username)
    