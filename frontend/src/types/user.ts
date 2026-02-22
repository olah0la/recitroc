import type { ID } from './common';

export interface User {
  id: ID;
  username: string;
  email: string;
  avatarUrl?: string;
}

export default User;
