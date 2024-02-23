import { InfoRounded } from '@mui/icons-material'
import { Link, Tooltip, Typography } from '@mui/material'

const TooltipImage = () => (
  <Tooltip
    sx={{ cursor: 'help' }}
    placement="bottom-end"
    title={
      <div>
        Image is optional and can be one of:
        <ul style={{ paddingLeft: '1rem' }}>
          <li>
            iconName{' '}
            <Link
              href="https://material-ui.com/components/material-icons/"
              target="_blank"
            >
              Find MUI icons here
            </Link>
            <Typography color="textSecondary" variant="subtitle1">
              <em>eg. flare, AccessAlarms</em>
            </Typography>
          </li>
          <li>
            mdi:icon-name{' '}
            <Link href="https://materialdesignicons.com" target="_blank">
              Find Material Design icons here
            </Link>
            <Typography color="textSecondary" variant="subtitle1">
              <em>eg. mdi:balloon, mdi:led-strip-variant</em>
            </Typography>
          </li>
          <li>
            image:custom-url
            <Typography
              color="textSecondary"
              variant="subtitle1"
              style={{ wordBreak: 'break-all' }}
            >
              <em>eg. image:file:///C:/Users/username/Pictures/scene.png</em> or
              <br />
              <em>
                image:https://i.ytimg.com/vi/4G2unzNoOnY/maxresdefault.jpg
              </em>
            </Typography>
          </li>
        </ul>
      </div>
    }
  >
    <InfoRounded />
  </Tooltip>
)

export default TooltipImage
