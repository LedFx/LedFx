const { Notification } = require('electron');

const NOTIFICATION_TITLE = 'LedFx Client - by Blade';
const NOTIFICATION_BODY = 'Testing Notification from the Main process';

function showNotification(title = NOTIFICATION_TITLE, body = NOTIFICATION_BODY) {
  new Notification({
    toastXml: `<toast>
       <visual>
         <binding template="ToastText02">
           <text id="1">LedFx Update available</text>
           <text id="2">Click the button to see more informations.</text>
         </binding>
       </visual>
       <actions>
         <action content="Goto Release" activationType="protocol" arguments="https://github.com/YeonV/LedFx-Builds/releases/latest" />
       </actions>
    </toast>`,
 }).show();
}

module.exports = { showNotification };