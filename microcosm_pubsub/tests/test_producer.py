"""
Producer tests.

"""
from json import loads
from os import environ

from hamcrest import (
    assert_that,
    calling,
    equal_to,
    is_,
    none,
    raises,
)
from microcosm.api import create_object_graph
from microcosm.loaders import load_from_environ
import microcosm.opaque  # noqa

from microcosm_pubsub.conventions import created
from microcosm_pubsub.errors import TopicNotDefinedError
from microcosm_pubsub.producer import DeferredProducer, iter_topic_mappings
from microcosm_pubsub.tests.fixtures import (
    FOO_TOPIC,
    FOO_MEDIA_TYPE,
    FooSchema,
    MESSAGE_ID,
)


def test_produce_no_topic_arn():
    """
    Producer delegates to SNS client.

    """
    def loader(metadata):
        return dict(
            pubsub_message_schema_registry=dict(
                default=FooSchema,
            ),
            sns_topic_arns=dict(
            ),
        )

    graph = create_object_graph("example", testing=True, loader=loader)
    assert_that(
        calling(graph.sns_producer.produce).with_args(FOO_MEDIA_TYPE, bar="baz"),
        raises(TopicNotDefinedError),
    )


def test_produce_default_topic():
    """
    Producer delegates to SNS client.

    """
    def loader(metadata):
        return dict(
            pubsub_message_codecs=dict(
                default=FooSchema,
            ),
            sns_topic_arns=dict(
                default=FOO_TOPIC,
            )
        )

    graph = create_object_graph("example", testing=True, loader=loader)
    graph.use("opaque")

    # set up response
    graph.sns_producer.sns_client.publish.return_value = dict(MessageId=MESSAGE_ID)

    message_id = graph.sns_producer.produce(FOO_MEDIA_TYPE, bar="baz")

    assert_that(graph.sns_producer.sns_client.publish.call_count, is_(equal_to(1)))
    assert_that(graph.sns_producer.sns_client.publish.call_args[1]["TopicArn"], is_(equal_to(FOO_TOPIC)))
    assert_that(loads(graph.sns_producer.sns_client.publish.call_args[1]["Message"]), is_(equal_to({
        "bar": "baz",
        "mediaType": "application/vnd.globality.pubsub.foo",
        "opaqueData": {},
    })))
    assert_that(message_id, is_(equal_to(MESSAGE_ID)))


def test_produce_custom_topic():
    """
    Producer delegates to SNS client.

    """
    def loader(metadata):
        return dict(
            pubsub_message_codecs=dict(
                default=FooSchema,
            ),
            sns_topic_arns=dict(
                default=None,
                mappings={
                    FOO_MEDIA_TYPE: FOO_TOPIC,
                },
            )
        )

    graph = create_object_graph("example", testing=True, loader=loader)
    graph.use("opaque")

    # set up response
    graph.sns_producer.sns_client.publish.return_value = dict(MessageId=MESSAGE_ID)

    message_id = graph.sns_producer.produce(FOO_MEDIA_TYPE, bar="baz")

    assert_that(graph.sns_producer.sns_client.publish.call_count, is_(equal_to(1)))
    assert_that(graph.sns_producer.sns_client.publish.call_args[1]["TopicArn"], is_(equal_to(FOO_TOPIC)))
    assert_that(loads(graph.sns_producer.sns_client.publish.call_args[1]["Message"]), is_(equal_to({
        "bar": "baz",
        "mediaType": "application/vnd.globality.pubsub.foo",
        "opaqueData": {},
    })))
    assert_that(message_id, is_(equal_to(MESSAGE_ID)))


def test_iter_topic_mappings():
    result = dict(
        iter_topic_mappings(
            dict(
                foo="bar",
                bar=dict(
                    foo="baz",
                ),
                baz=dict(
                    foo=dict(
                        bar="foo",
                    ),
                ),
            )
        )
    )
    assert_that(result, is_(equal_to({
        "foo": "bar",
        "bar.foo": "baz",
        "baz.foo.bar": "foo",
    })))


def test_produce_custom_topic_environ():
    """
    Can set a custom topic via environment

    """
    key = "EXAMPLE__SNS_TOPIC_ARNS__CREATED__FOO__BAR_BAZ"
    environ[key] = "foo-topic"
    graph = create_object_graph("example", testing=True, loader=load_from_environ)
    graph.sns_producer.produce(created("foo.bar_baz"), bar="baz")
    assert_that(graph.sns_producer.sns_client.publish.call_count, is_(equal_to(1)))
    assert_that(graph.sns_producer.sns_client.publish.call_args[1]["TopicArn"], is_(equal_to(FOO_TOPIC)))


def test_deferred_production():
    """
    Deferred production waits until the end of a block.

    """
    def loader(metadata):
        return dict(
            pubsub_message_codecs=dict(
                default=FooSchema,
            ),
            sns_topic_arns=dict(
                default=FOO_TOPIC,
            )
        )

    graph = create_object_graph("example", testing=True, loader=loader)
    graph.use("opaque")

    # set up response
    graph.sns_producer.sns_client.publish.return_value = dict(MessageId=MESSAGE_ID)

    with DeferredProducer(graph.sns_producer) as producer:
        assert_that(producer.produce(FOO_MEDIA_TYPE, bar="baz"), is_(none()))

        assert_that(graph.sns_producer.sns_client.publish.call_count, is_(equal_to(0)))

    assert_that(graph.sns_producer.sns_client.publish.call_count, is_(equal_to(1)))
