from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["use_jalali_calendar"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["use_jalali_calendar"]

    use_jalali_calendar = fields.Boolean(
        string="Use Jalali Calendar",
        default=False,
        help="When enabled, dates are displayed and selected using the Jalali calendar.",
        groups="base.group_user",
    )

    @api.model
    def get_current_user_jalali_flag(self):
        user = self.env.user
        return {
            "use_jalali_calendar": bool(user.use_jalali_calendar),
        }

    def action_toggle_jalali_calendar(self):
        """Toggle Jalali flag for the current user only.

        Works for normal users by elevating only for this write.
        """
        user = self.env.user.sudo()
        user.use_jalali_calendar = not bool(user.use_jalali_calendar)
        return True
