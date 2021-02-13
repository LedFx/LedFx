import React from 'react';

import { IconButton } from '@material-ui/core';
import GitHubIcon from '@material-ui/icons/GitHub';
import LanguageIcon from '@material-ui/icons/Language';
import ForumIcon from '@material-ui/icons/Forum';
import BugTracker from 'components/BugTracker';

const BottomBar = ({ classes }) => {
    return (
        <div className={classes.bottomBar}>
            <IconButton
                aria-label="Website"
                color="inherit"
                href="https://ledfx.app/"
                target="_blank"
                title="Website"
            >
                <LanguageIcon />
            </IconButton>
            <IconButton
                aria-label="Github"
                color="inherit"
                href="https://git.ledfx.app/"
                target="_blank"
                title="Github"
            >
                <GitHubIcon />
            </IconButton>
            <IconButton
                aria-label="Discord"
                color="inherit"
                href="https://discord.gg/tFSKgTzRcj"
                target="_blank"
                title="Discord"
            >
                <ForumIcon />
            </IconButton>
            {parseInt(window.localStorage.getItem('BladeMod')) >= 2 && (
                <BugTracker color="inherit" />
            )}
        </div>
    );
};

export default BottomBar;
