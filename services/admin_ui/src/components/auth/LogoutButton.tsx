import { useAuth0 } from '@auth0/auth0-react';
import { Button } from '@/components/ui/button';

const LogoutButton = () => {
  const { logout } = useAuth0();
  return <Button variant="outline" onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}>
    Logga ut
  </Button>;
};

export default LogoutButton; 