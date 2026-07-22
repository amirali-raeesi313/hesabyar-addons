# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ErpAutoNotify(models.AbstractModel):
    """اعلان یکپارچه: پیام به کانال گفتگو (و بعداً پیامک/ایمیل از همین نقطه)."""
    _name = "erp.auto.notify"
    _description = "اعلان اتوماسیون"

    def post_channel(self, channel_name, body):
        channel = self.env["discuss.channel"].sudo().search(
            [("name", "=", channel_name)], limit=1)
        if not channel:
            channel = self.env["discuss.channel"].sudo().create({
                "name": channel_name, "channel_type": "channel",
            })
        channel.message_post(
            body=body.replace("\n", "<br/>"),
            message_type="comment", subtype_xmlid="mail.mt_comment")
        return channel

    def notify_users(self, users, subject, body):
        for user in users:
            user.partner_id.message_post(body="<b>%s</b><br/>%s" % (subject, body))
        return True
