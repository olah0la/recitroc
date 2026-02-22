import { User } from './user'
import { Item } from './item'
import { ID, Auditable } from './common';

export interface Trade extends Auditable {
  id: ID;
  itemOffered: Item;
  itemRequested: Item;
  proposer: User;
  responder: User;
  status: 'pending' | 'accepted' | 'rejected';
}

export default Trade;