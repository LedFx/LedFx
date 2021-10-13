import { useSelector, useDispatch } from 'react-redux';
import Button from '@material-ui/core/Button';
import pkceChallenge from 'pkce-challenge';
import Cookies from 'universal-cookie/es6';
import { Grid, Typography } from '@material-ui/core';
import { checkCookiesForTokens, finishAuth, refreshAuth, logoutAuth } from 'modules/spotify';
import { editAsyncIntegration } from 'modules/integrations';

//import SpotifyPlayer from 'components/SpotifyPlayer';
//import TriggersList from 'components/TriggersList';
import { useEffect } from 'react';

const SpotifyView = props => {
    //const { spotify, refreshAuth } = this.props;
    const spotify = useSelector(state => state.spotify);
    const dispatch = useDispatch();

    const beginAuth = () => {
        const codes = pkceChallenge();
        const cookies = new Cookies();
        cookies.set('verifier', codes.code_verifier);
        let authURL =
            `https://accounts.spotify.com/authorize/` +
            '?response_type=code' +
            '&client_id=' +
            encodeURIComponent('7658827aea6f47f98c8de593f1491da5') +
            '&scope=' +
            encodeURIComponent(
                'user-library-read user-library-modify user-read-email user-top-read streaming user-read-private user-read-playback-state user-modify-playback-state'
            ) +
            '&redirect_uri=' +
            encodeURIComponent('http://localhost:3000/integrations/') +
            '&code_challenge=' +
            encodeURIComponent(codes.code_challenge) +
            '&code_challenge_method=S256';
        console.log(authURL);
        window.location.href = authURL;
    };

    useEffect(() => {
        const cookies = new Cookies();
        const accessTest = cookies.get('logout');
        const accessTest1 = cookies.get('access_token');
        if ((accessTest == 'false' || !accessTest) && !accessTest1) {
            dispatch(refreshAuth());
            cookies.set('logout', false);
        }
        console.log('Got to useEffect:', window.location.search);
        if (window.location.search) {
            console.log('Got to here');
            dispatch(finishAuth());
        }
        dispatch(editAsyncIntegration());
        dispatch(checkCookiesForTokens());
    }, []);

    const logoutClick = () => {
        dispatch(logoutAuth());
        dispatch(editAsyncIntegration());
    };

    return (
        <Grid container justify="center" alignContent="center" style={{ height: '10%' }}>
            {!spotify.accessToken && !spotify.refreshToken ? (
                <Button variant="contained" color="primary" onClick={() => beginAuth()}>
                    <Typography>Connect to Spotify</Typography>
                </Button>
            ) : spotify.accessToken ? (
                <Button variant="contained" color="primary" onClick={() => logoutClick()}>
                    <Typography>Logout</Typography>
                </Button>
            ) : (
                ''
            )}
        </Grid>
    );
};

export default SpotifyView;
