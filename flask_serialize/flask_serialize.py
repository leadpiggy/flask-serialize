from datetime import datetime, time

from flask import request, jsonify, abort, current_app
from permissive_dict import PermissiveDict


class FlaskSerializeMixin:
    """
    Base mix in class to implement serialization and update methods for use
    with Flask and SQL Alchemy models
    """
    # fields that should not be exposed by serialization
    __fs_exclude_serialize_fields__ = []
    __fs_exclude_json_serialize_fields__ = []
    # list of fields to be used when updating
    __fs_update_fields__ = []
    # list of fields used when creating
    __fs_create_fields__ = []
    # order by ascending field
    __fs_order_by_field__ = None
    __fs_order_by_field_desc__ = None
    # default error code
    __fs_http_error_code = 400
    # list of fields used to set the update date/time
    __fs_timestamp_fields__ = ['updated', 'timestamp']
    # method to be used to timestamp with____fs_update_timestamp__ method__
    __fs_timestamp_stamper__ = datetime.utcnow
    # list of property names that are relationships to be included in serialization
    __fs_relationship_fields__ = []
    # add your own converters here
    __fs_column_type_converters__ = {}
    # add or replace conversion types
    __fs_convert_types__ = [{'type': bool, 'method': lambda v: 'y' if v else 'n'},
                            {'type': bytes, 'method': lambda v: v.encode()}]
    __fs_json_types = [str, dict, list, int, float, bool]
    # default field name when restricting to a particular user
    __fs_user_field__ = 'user'
    # properties or fields to return when updating using get or post
    __fs_update_properties__ = []
    # db is required to be set for updating/deletion functions
    db = None
    # cache model properties
    __model_props = {}
    # previous values of an instance before update attempted
    __fs_previous_field_value__ = {}
    # current version
    __version__ = '2.0.1'

    def __fs_before_update__(self, data_dict):
        """
        hook to call before any__fs_update_from_dict so that you may alter update values__
        before the item is written in preparation for update to db

        :param data_dict: the new data to apply to the item
        :return: the new data_dict to use for updating
        """
        return data_dict

    def __fs_after_commit__(self, create=False):
        """
        hook to call after any put/post commit so that you may do something
        self will be the new / updated committed item

        :param create: True when item was just created.
        """

    def __fs_to_date_short__(self, d):
        """
        convert the given date field to a short date / time without fractional seconds

        :param d: {datetime.datetime} the value to convert
        :return: {String} the short date
        """
        return str(d).split('.')[0]

    @classmethod
    def fs_query_by_access(cls, user=None, **kwargs):
        """
        filter a query result to that optionally owned by the given user and
        __fs_can_access__()

        :param user: the user to use as a filter, default relationship name is user (__fs_user_field__)
        :return: a list of query results
        """

        if user:
            kwargs[cls.__fs_user_field__] = user

        query = cls.query.filter_by(**kwargs)
        items = [item for item in query if item.__fs_can_access__()]

        return items

    @classmethod
    def fs_get_by_user_or_404(cls, item_id, user=None):
        """
        return the object with the given primary key id that is optionally owned by the given user and
        __fs_can_access__()

        :param item_id: object primary key, id
        :param user: the user to use as a filter, default relationship name is user (__fs_user_field__)
        :return: the object
        :throws: 404 exception if not found
        """

        kwargs = {'id': item_id}
        if user:
            kwargs[cls.__fs_user_field__] = user
        item = cls.query.filter_by(**kwargs).first_or_404()
        if not item.__fs_can_access__():
            abort(404)
        return item

    @classmethod
    def fs_json_filter_by(cls, **kwargs):
        """
        return a list in json format using the filter_by arguments

        :param kwargs: SQLAlchemy query.filter_by arguments
        :return: flask response with json list of results
        """
        results = cls.query.filter_by(**kwargs)
        return cls.fs_json_list(results)

    @classmethod
    def fs_json_get(cls, item_id):
        """
        return an item in json format using the item_id as a primary key

        :param item_id: {primary key} the primary key of the item to get
        :return: flask response with json item, or {} if not found or no access
        """
        item = cls.query.get(item_id)
        if not item or not item.__fs_can_access__():
            return jsonify({})
        return item.fs_as_json

    @classmethod
    def fs_json_list(cls, query_result, prop_filters=None):
        """
        Return a list in json format from the query_result.
        When __fs_order_by_field__ is defined sort by that field in ascending order.
        Only returns those that __fs_can_access__()

        :param query_result: sql alchemy query result
        :param prop_filters: dictionary of filter elements to restrict results
        :return: flask response with json list of results
        """
        # ascending
        items = [item.__as_exclude_json_dict() for item in query_result if item.__fs_can_access__()]

        if len(items) > 0 and cls.__fs_order_by_field__:
            items = sorted(items, key=lambda i: i[cls.__fs_order_by_field__])

        # descending
        if len(items) > 0 and cls.__fs_order_by_field_desc__:
            items = sorted(items, key=lambda i: i[cls.__fs_order_by_field_desc__], reverse=True)

        if prop_filters:
            filtered_result = []
            for item in items:
                for k, v in prop_filters.items():
                    if item.get(k) == v:
                        filtered_result.append(item)
                        break
            items = filtered_result

        return jsonify(items)

    @classmethod
    def fs_dict_list(cls, query_result):
        """
        return a list of dictionary objects from the sql query result
        without __fs_exclude_serialize_fields__ fields
        for only those than __fs_can_access__()

        :param query_result: sql alchemy query result
        :return: list of dict objects
        """
        return [item.__as_exclude_json_dict() for item in query_result if item.__fs_can_access__()]

    @property
    def fs_as_json(self):
        """
        the sql object as a json response without the excluded fields

        :return: flask response json object
        """
        return jsonify(self.__as_exclude_json_dict())

    def fs_private_field(self, field_name):
        """
        return true if field_name should be private

        :param field_name: name to check
        :return:
        """
        return False

    def __as_exclude_json_dict(self):
        """
        private: get a dict that is used to serialize to web clients
        without fields in __fs_exclude_json_serialize_fields__ and __fs_exclude_serialize_fields__
        excludes any private_field

        :return: dictionary
        """
        return {k: v for k, v in self.fs_as_dict.items() if
                k not in self.__fs_exclude_json_serialize_fields__}

    def __fs_property_converter__(self, value):
        """
        convert to a json compatible format.

        * complex - just uses str conversion
        * datetime - short format as per  __fs_to_date_short__
        * set - becomes a list
        * anything else not supported by json becomes a str

        override or extend this method to alter defaults

        :param value: value to convert
        :return: the new value
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return self.__fs_to_date_short__(value)
        if isinstance(value, set):
            return list(value)
        if isinstance(value, FlaskSerializeMixin):
            return value.fs_as_dict
        if type(value) not in self.__fs_json_types:
            return str(value)
        return value

    @staticmethod
    def __relationship_converter(relationships):
        """
        convert a child SQLAlchemy result set into a python
        dictionary list.

        :param relationships: SQLAlchemy result set
        :return: list of dict objects
        """
        if isinstance(relationships, FlaskSerializeMixin):
            return relationships.fs_as_dict
        return [item.fs_as_dict for item in relationships]

    @staticmethod
    def __lob_converter(value):
        """
        convert a LOB into a decoded string

        :param value: lob to convert
        :return: decoded string
        """
        if not value:
            return ''
        value = value.decode()
        return value

    @staticmethod
    def __sqlite_date_converter(value):
        """
        convert an ISO-9 date or datetime from a form etc into a datetime as sqlite does
        not handle date conversions nicely

        :param value: form / json data to convert
        :return: corrected datetime or time
        """
        if isinstance(value, datetime) or isinstance(value, time):
            return value
        # assumes ISO 8601 as per javascript standard for dates
        try:
            return datetime.strptime(value, '%Y-%m-%dT%H:%M')
        except:
            return datetime.strptime(value, '%Y-%m-%d')

    def __get_props(self):
        """
        get the properties for this table to be used for introspection

        :return: properties EasyDict
        """
        props = self.__model_props.get(self.__table__)
        if not props:
            props = PermissiveDict(name=self.__table__.name, id=0, primary_key_field='id')
            props.converters = {'DATETIME': self.__fs_to_date_short__,
                                'PROPERTY': self.__fs_property_converter__,
                                'RELATIONSHIP': self.__relationship_converter,
                                'NUMERIC': float,
                                'DECIMAL': float,
                                'LOB': self.__lob_converter,
                                'BLOB': self.__lob_converter,
                                'CLOB': self.__lob_converter,
                                }

            # SQL columns
            props.__exclude_fields = ['fs_as_dict', 'fs_as_json'] + self.__fs_exclude_serialize_fields__
            field_list = list(self.__table__.columns)
            if 'sqlite' in self.__table__.dialect_options:
                props.DIALECT = 'sqlite'
                self.__fs_convert_types__.append(
                    {'type': datetime, 'method': self.__sqlite_date_converter}),
            # detect primary field
            for f in field_list:
                if f.primary_key:
                    props.id = str(getattr(self, f.name, ''))
                    props.primary_key_field = f.name
                    break

            # add class properties
            field_list += [PermissiveDict(name=p, type='PROPERTY') for p in dir(self.__class__) if
                           isinstance(getattr(self.__class__, p), property)]
            # add relationships
            field_list += [PermissiveDict(name=p, type='RELATIONSHIP') for p in self.__fs_relationship_fields__]
            # add custom converters
            for converter, method in self.__fs_column_type_converters__.items():
                props.converters[converter] = method
            # exclude fields / props
            props.field_list = []
            for f in field_list:
                if f.name not in props.__exclude_fields:
                    f.c_type = str(f.type).split('(')[0]
                    f.converter = props.converters.get(f.c_type)
                    if not f.converter:
                        # any non json supported types gets a str
                        if getattr(f.type, 'python_type', None) not in self.__fs_json_types:
                            f.converter = str
                    props.field_list.append(f)

            self.__model_props[self.__table__] = props
        return props

    def __get_fields(self):
        """
        return a list of field objects that are valid
        using fs_private_field
        [{name,c__type,converter},...]

        :return:
        """
        fields = []
        for c in self.__get_props().field_list:
            if not self.fs_private_field(c.name):
                fields.append(c)
        return fields

    @property
    def fs_as_dict(self):
        """
        convert a sql alchemy query result item to dict
        override these properties to control the result:

        * __fs_relationship_fields__ - follow relationships listed
        * __fs_exclude_serialize_fields__ - exclude listed fields from serialization
        * __fs_column_type_converters__ - add additional sql column type converters to DATETIME, PROPERTY and RELATIONSHIP
        :return {dictionary} the item as a dict
        """

        # built in converters
        # can be replaced using __fs_column_type_converters__
        d = {}

        for c in self.__get_fields():
            try:
                d[c.name] = v = getattr(self, c.name, '')
            except Exception as e:
                v = str(e)

            if v is None:
                d[c.name] = ''
            elif c.converter:
                try:
                    d[c.name] = c.converter(v)
                except Exception as e:
                    d[c.name] = 'Error:"{}". Failed to convert [{}] type:{}'.format(e, c.name, c.c_type)
        return d

    def __json_api_dict(self):
        """
        start of returning as JSON_API.  Unused

        :return: {id, name, attributes(dict)}
        """
        props = self.__get_props()
        d = dict(id=props.id, type=props.name, attributes=self.fs_as_dict)
        return jsonify(d)

    def __json_api_list(self, query_result):
        """
        start of returning as JSON_API.  Unused
        returns a list of items where __fs_can_access__() from query_result

        :param query_result:
        :return: list of {id, name, attributes(dict)}
        """
        fs_dict_list = self.fs_dict_list(query_result=query_result)
        d = dict(data=[item.__json_api_dict() for item in fs_dict_list])
        return jsonify(d)

    def __get_update_field_type(self, field, value):
        """
        get the type of the update to db field from cached table properties

        :param field:
        :return: class of the type
        """
        props = self.__get_props()
        if props:
            for f in props.field_list:
                if f.name == field:
                    if f.c_type.startswith("VARCHAR") or f.c_type.startswith("CHAR") or f.c_type.startswith("TEXT"):
                        return str
                    if f.c_type.startswith("INTEGER"):
                        return int
                    if f.c_type.startswith("FLOAT") or f.c_type.startswith("REAL") or f.c_type.startswith("NUMERIC"):
                        return float
                    if f.c_type.startswith("DATE") or f.c_type.startswith("TIME"):
                        return datetime
                    if f.c_type.startswith("BOOLEAN"):
                        return bool
                    if 'LOB' in f.c_type:
                        return bytes

        return None

    def __convert_value(self, name, value):
        """
        convert the value based upon type to a representation suitable for saving to the db
        override built in conversions by setting the value of __fs_convert_types__.
        First uses bare value to determine type and then uses db derived values
        ie:
        __fs_convert_types__ = [{'type':bool, 'method': lambda x: not x}]

        :param name: name of the field to update
        :param value: value to update with
        :return: the converted value
        """
        for t in self.__fs_convert_types__:
            if isinstance(value, t['type']):
                value = t['method'](value)
                return value

        instance_type = self.__get_update_field_type(name, value)
        if instance_type:
            for t in self.__fs_convert_types__:
                if instance_type == t['type']:
                    value = t['method'](value)
                    return value
        return value

    @classmethod
    def fs_request_create_form(cls, **kwargs):
        """
        create a new item from a form in the current request object
        throws error if something wrong. Use **kwargs to set the object properties of the newly created item.

        :return: the new created item
        """
        new_item = cls(**kwargs)

        __fs_create_fields__ = list(new_item.__fs_create_fields__)
        if len(__fs_create_fields__ or '') == 0:
            __fs_create_fields__ = [c.name for c in new_item.__get_fields() if
                                    isinstance(c, cls.db.Column) and c.name != new_item.__get_props().primary_key_field]

        try:
            json_data = request.get_json(force=True)
            if len(json_data) > 0:
                for field in __fs_create_fields__:
                    if cls.db and isinstance(field, cls.db.Column):
                        field = field.name
                    if field in json_data:
                        value = json_data.get(field)
                        setattr(new_item, field, new_item.__convert_value(field, value))
        except:
            for field in __fs_create_fields__:
                if cls.db and isinstance(field, cls.db.Column):
                    field = field.name
                if field in request.form:
                    value = request.form.get(field)
                    setattr(new_item, field, new_item.__convert_value(field, value))

        new_item.__fs_verify__(create=True)
        new_item.__fs_update_timestamp__()
        cls.db.session.add(new_item)
        cls.db.session.commit()
        new_item.__fs_after_commit__(create=True)
        return new_item

    def fs_request_update_form(self):
        """
        update/create the item using form data from the request object
        only present fields are updated
        throws error if validation or __fs_can_update__() fails

        :return: True when complete
        """
        if request.content_type == 'application/json' or request.method == 'PUT':
            return self.fs_request_update_json()
        else:
            self.fs_update_from_dict(request.form)
        if not self.__fs_can_update__():
            return False
        self.__fs_verify__()
        self.__fs_update_timestamp__()
        if not self.db:
            raise Exception('FlaskSerializeMixin property "db" is not set')
        self.db.session.add(self)
        self.db.session.commit()
        self.__fs_after_commit__(self)
        return True

    def fs_request_update_json(self):
        """
        Update an item from request json data or PUT params, probably from a PUT or PATCH.
        Throws exception if not valid or __fs_can_update__() fails

        :return: True if item updated
        """

        if not self.__fs_can_update__():
            return False
        try:
            json_data = request.get_json(force=True)
        except Exception as e:
            json_data = request.values
            if len(json_data) == 0:
                current_app.logger.exception(e)

        self.fs_update_from_dict(json_data)

        self.__fs_verify__()
        self.__fs_update_timestamp__()
        if not self.db:
            raise Exception('FlaskSerializeMixin property "db" is not set')
        self.db.session.add(self)
        self.db.session.commit()
        self.__fs_after_commit__()
        return True

    def __fs_update_timestamp__(self):
        """
        update any timestamp fields using the Class timestamp method if those fields exist

        """
        for field in self.__fs_timestamp_fields__:
            if hasattr(self, field):
                setattr(self, field, self.__fs_timestamp_stamper__())

    def fs_update_from_dict(self, data_dict):
        """
        uses a dict to update fields of the model instance.  sets previous values to
        self.previous_values[field_name] before the update

        :param data_dict: the data to update
        :return:
        """
        data_dict = self.__fs_before_update__(data_dict)
        __fs_update_fields__ = list(self.__fs_update_fields__)
        if len(self.__fs_update_fields__ or '') == 0:
            __fs_update_fields__ = [c.name for c in self.__get_fields() if
                                    isinstance(c, self.db.Column) and c.name != self.__get_props().primary_key_field]
        for field in __fs_update_fields__:
            if self.db and isinstance(field, self.db.Column):
                field = field.name
            self.__fs_previous_field_value__[field] = getattr(self, field)
            if field in data_dict:
                setattr(self, field, self.__convert_value(field, data_dict[field]))

    def __fs_can_access__(self):
        """
        hook to see if can access
        return True if allowed to access, return false if not

        :return: True/False
        """
        return True

    def __fs_can_update__(self):
        """
        hook to see if can update
        return True if allowed to update, raise an error if not allowed

        :return: True if can update
        """
        return self.__fs_can_access__()

    def __fs_can_delete__(self):
        """
        hook to see if can delete
        raise an exception if deletion is not allowed or True
        if deletion is allowed.  Default is __fs_can_update__() returns false
        aborts with 403

        :return: True if can delete
        """
        if not self.__fs_can_update__():
            abort(403)
        return True

    def __fs_verify__(self, create=False):
        """
        hook to verify item
        raise exception if item is not valid for put/patch/post

        :param: create - True if verification is for a new item
        """
        pass

    def __return_properties(self):
        """
        when returning success codes from a put/post update return a dict
        composed of the property values from the __fs_update_properties__ list.
        ie:
        return jsonify({'message': 'Updated', 'properties': item.__return_properties()})
        this can be used to communicate from the model on the server to the JavaScript code
        interesting things from updates, by default returns all accessible fields / properties.

        :return: dictionary of properties
        """
        return {prop: self.__fs_property_converter__(getattr(self, prop)) for prop in self.__fs_update_properties__}

    @classmethod
    def fs_get_delete_put_post(cls, item_id=None, user=None, prop_filters=None):
        """
        get, delete, post, put with JSON/FORM a single model item

        * any access uses __fs_can_access__() to check for accessibility
        * any update uses __fs_can_update__() to check for update permission

        :param item_id: the primary key of the item - if none and method is 'GET' returns all items
        :param user: user to use as query filter.
        :param prop_filters: dictionary of key:value pairs to limit results to.
        :return: json object: {message}, or the item.  throws error when problem
        """
        item = None
        if user is not None and item_id is not None:
            item = cls.fs_get_by_user_or_404(item_id, user=user)
        elif item_id is not None:
            item = cls.query.get_or_404(item_id)
            if not item.__fs_can_access__():
                abort(404)
        elif request.method == 'GET':
            # no item id get a list of items
            if user:
                kwargs = {cls.__fs_user_field__: user}
                result = cls.query.filter_by(**kwargs)
            else:
                result = cls.query.all()
            return cls.fs_json_list(result, prop_filters=prop_filters)

        try:
            if not item:
                if request.method == 'POST':
                    return cls.fs_request_create_form().fs_as_json
                abort(405)

            # get a single item
            if request.method == 'GET':
                return item.fs_as_json

            elif request.method == 'POST' or request.method == 'PUT':
                # update single item
                item.fs_request_update_form()
                return jsonify(
                    dict(message='Updated', item=item.__as_exclude_json_dict(), properties=item.__return_properties()))

            elif request.method == 'DELETE':
                # delete a single item
                item.__fs_can_delete__()
                cls.db.session.delete(item)
                cls.db.session.commit()
                return jsonify(dict(item=item.fs_as_dict, message='Deleted'))

        except Exception as e:
            return str(e), cls.__fs_http_error_code

    @classmethod
    def fs_json_first(cls, **kwargs):
        """
        return the first result in json response format using the filter_by arguments, or {} if no result
        or not __fs_can_access__()

        :param kwargs: SQLAlchemy query.filter_by arguments
        :return: flask response json item or {} if no result
        """
        item = cls.query.filter_by(**kwargs).first()
        if not item or not item.__fs_can_access__():
            return jsonify({})

        return item.fs_as_json


def FlaskSerialize(db=None):
    """
    Factory to 
    return the FlaskSerializeMixin mixin class, optionally initialize the db values

    :param db: (optional) SQLAlchemy db instance
    :return: FlaskSerializeMixin mixin
    """
    FlaskSerializeMixin.db = db
    return FlaskSerializeMixin
