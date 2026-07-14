export interface User {
  /** The email is the user's primary key — there is no numeric id. */
  email: string;
  username?: string;
  firstName?: string;
  lastName?: string;
  avatarUrl?: string;
}

export default User;
