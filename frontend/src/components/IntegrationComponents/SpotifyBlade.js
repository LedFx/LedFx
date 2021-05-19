import { useSelector } from 'react-redux';
import Button from '@material-ui/core/Button';
import pkceChallenge from 'pkce-challenge';
import Cookies from 'universal-cookie/es6';
import { Grid, Typography } from '@material-ui/core';
import { checkCookiesForTokens, finishAuth, refreshAuth  } from 'modules/spotify'
import SpotifyPlayer from 'components/SpotifyPlayer';
import TriggersList from 'components/TriggersList';

const SpotifyView = (props)=> {
    
    const { spotify, refreshAuth } = props;
    const spotify = useSelector(state => state.spotify);
    
    const beginAuth = () => {
        const codes = pkceChallenge();
        const cookies = new Cookies();
        cookies.set('verifier', codes.code_verifier)
        let authURL = 
            `https://accounts.spotify.com/authorize/`
            + "?response_type=code"
            + "&client_id="+encodeURIComponent('7658827aea6f47f98c8de593f1491da5')
            + "&scope="+encodeURIComponent('user-library-read user-library-modify user-read-email user-top-read streaming user-read-private user-read-playback-state user-modify-playback-state')
            + "&redirect_uri="+encodeURIComponent('http://localhost:3000/integrations/')
            + "&code_challenge="+encodeURIComponent(codes.code_challenge)
            + "&code_challenge_method=S256"
            ;
        console.log(authURL)
        window.location.href = authURL 
    }

    useEffect(() => {
        if (window.location.search) {
            finishAuth()
        }
        checkCookiesForTokens()     
    }, [])    
    
    return (
        <Grid container justify='center' alignContent='center' style={{height: '10%'}}>
            {!spotify.accessToken && !spotify.refreshToken ? 
            <Button variant='contained' color="primary" onClick={() => beginAuth()}>
                <Typography>1Connect to Spotify</Typography>
            </Button> 
            : 
                !spotify.accessToken && spotify.refreshToken ? 
                <Button variant='contained' color="primary" onClick={() => refreshAuth()}>
                    <Typography>Reconnect to Spotify</Typography>
                </Button>
                : 
                <div style={{width: '100%'}}>
                    <SpotifyPlayer />
                    <TriggersList />
                </div>
            }
        </Grid>
    );
    
}

export default SpotifyView;
